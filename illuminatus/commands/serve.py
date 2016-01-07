import bottle
import climate
import datetime
import io
import multiprocessing as mp
import os
import sys

from illuminatus import db, export
from illuminatus.util import parse, stringify, tag_sort_key, tag_class

cmd = climate.add_command('serve')
cmd.add_argument('--host', default='localhost',
                 help='run server on this hostname')
cmd.add_argument('--port', type=int, default=5555, metavar='N',
                 help='run server on port N')
cmd.add_argument('--reload', action='store_true',
                 help='reload server whenever modules change')
cmd.add_argument('--workers', type=int, default=1, metavar='N',
                 help='launch N workers starting at the given port')
cmd.set_defaults(mod=sys.modules[__name__])

posted_float = lambda k: float(bottle.request.forms.get(k))


@bottle.get('/')
def index():
    return bottle.static_file('index.html', os.curdir)

@bottle.get('/static/<path:path>')
def static(path):
    return bottle.static_file(path, os.curdir)

@bottle.get('/img/<path:path>')
def image(path):
    try:
        res = bottle.static_file(path, os.path.dirname(db.DB))
        res.set_header('Cache-Control', 'no-cache')
        return res
    except:
        pass


@bottle.get('/tags')
def tags():
    return stringify([dict(name=t, key=tag_sort_key(t), meta=tag_class(t))
                      for t in db.tag_names()])


@bottle.get('/media')
def list_media():
    req = bottle.request
    tags = tuple(t.strip() for t in req.query.tags.split('|') if t.strip())
    return stringify(
        [m.to_dict() for m in db.find(
            tags=tags,
            offset=int(req.query.offset or 0),
            limit=int(req.query.limit or 10))])

@bottle.get('/media/<id:int>')
def read_media(id):
    return stringify(db.find_one(id).to_dict())

@bottle.get('/media/export')
def download_media():
    q = bottle.request.query
    media = None
    if q.ids:
        media = db.find(ids=list(map(int, q.ids.split(','))))
    elif q.tags:
        media = db.find(tags=q.tags.split('|'))
    buf = io.BytesIO()
    export.export(
        list(media),
        output=buf,
        sizes=list(map(int, (q.size or '').split(','))),
        hide_tags=(q.hide or '').split('|'),
        exif_tags=bool(q.exif),
        datetime_tags=bool(q.datetime),
        omnipresent_tags=bool(q.omnipresent),
    )
    fn = 'media-{}.zip'.format(datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    res = bottle.response
    res.set_header('Content-Type', 'application/zip; charset=UTF-8')
    res.set_header('Content-Disposition', 'attachment; filename="{}"'.format(fn))
    return buf.getvalue()


@bottle.put('/media/<id:int>')
def update_media(id):
    m = db.find_one(id)
    f = bottle.request.forms
    # so annoying! https://github.com/defnull/bottle/issues/339
    f = dict((k, f.getunicode(k)) for k in f)
    modified = False
    if 'stamp' in f:
        m.meta['stamp'] = f['stamp']
        modified = True
    if 'tags' in f:
        m.meta['userTags'] = f['tags'].split('|')
        modified = True
    if modified:
        db.update(m)
    return stringify(m.to_dict())


@bottle.delete('/media/<id:int>')
def delete_media(id):
    m = db.find_one(id)
    db.delete(m.id, m.path)

@bottle.delete('/media/<id:int>/ops/<idx:int>-<key>')
def delete_op(id, idx, key):
    m = db.find_one(id)
    m.remove_op(idx, key)
    return stringify(m.to_dict())


@bottle.post('/photos/<id:int>/rotate')
def rotate_photo(id):
    m = db.find_one(id)
    m.rotate(degrees=posted_float('degrees'))
    return stringify(m.to_dict())

@bottle.post('/photos/<id:int>/brightness')
def brightness_photo(id):
    m = db.find_one(id)
    m.brightness(level=posted_float('level'))
    return stringify(m.to_dict())

@bottle.post('/photos/<id:int>/contrast')
def contrast_photo(id):
    m = db.find_one(id)
    m.contrast(level=posted_float('level'))
    return stringify(m.to_dict())

@bottle.post('/photos/<id:int>/saturation')
def saturation_photo(id):
    m = db.find_one(id)
    m.saturation(level=posted_float('level'))
    return stringify(m.to_dict())

@bottle.post('/photos/<id:int>/crop')
def crop_photo(id):
    m = db.find_one(id)
    m.crop(box=[posted_float(k) for k in 'x1 y1 x2 y2'.split()])
    return stringify(m.to_dict())

@bottle.post('/photos/<id:int>/autocontrast')
def autocontrast_photo(id):
    m = db.find_one(id)
    m.autocontrast()
    return stringify(m.to_dict())


@bottle.get('/<path:path>')
def catchall(path):
    return bottle.static_file('index.html', os.curdir)


def run(host, port, reload):
    bottle.run(host=host, port=port, reloader=reload)


def main(args):
    workers = []
    for port in range(args.port, args.port + args.workers):
        a = args.host, port, args.reload
        workers.append(mp.Process(target=run, args=a))
    [w.start() for w in workers]
    try:
        [w.join() for w in workers]
    except:
        [w.terminate() for w in workers]
        raise

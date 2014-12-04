import bottle
import climate
import collections
import multiprocessing as mp
import os
import random
import sys

from lmj.media import db
from lmj.media.util import parse, stringify, tag_sort_key, tag_class

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
        return bottle.static_file(path, os.path.dirname(db.DB))
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


@bottle.put('/media/<id:int>')
def update_media(id):
    m = db.find_one(id)
    f = parse(list(bottle.request.forms)[0])
    modified = False
    if 'stamp' in f:
        m.meta['stamp'] = f['stamp']
        modified = True
    if 'userTags' in f:
        m.meta['userTags'] = f['userTags']
        modified = True
    if modified:
        db.update(m)
    return stringify(m.to_dict())


@bottle.delete('/media/<id:int>')
def delete_media(id):
    m = db.find_one(id)
    db.delete(m.id, m.path)


@bottle.post('/photos/<id:int>/rotate')
def rotate_photo(id):
    db.find_one(id).rotate(degrees=posted_float('degrees'))
    return 'ok'

@bottle.post('/photos/<id:int>/brightness')
def brightness_photo(id):
    db.find_one(id).brightness(level=posted_float('level'))
    return 'ok'

@bottle.post('/photos/<id:int>/contrast')
def contrast_photo(id):
    db.find_one(id).contrast(level=posted_float('level'))
    return 'ok'

@bottle.post('/photos/<id:int>/saturation')
def saturation_photo(id):
    db.find_one(id).saturation(level=posted_float('level'))
    return 'ok'

@bottle.post('/photos/<id:int>/crop')
def crop_photo(id):
    db.find_one(id).crop(box=[posted_float(k) for k in 'x1 y1 x2 y2'.split()])
    return 'ok'

@bottle.post('/photos/<id:int>/autocontrast')
def autocontrast_photo(id):
    db.find_one(id).autocontrast()
    return 'ok'


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

import bottle
import climate
import collections
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
cmd.set_defaults(mod=sys.modules[__name__])


@bottle.get('/')
def main():
    return bottle.static_file('index.html', os.curdir)

@bottle.get('/static/<path:path>')
def static(path):
    return bottle.static_file(path, os.curdir)

@bottle.get('/img/<path:path>')
def image(path):
    return bottle.static_file(path, os.path.dirname(db.DB))


@bottle.get('/tag-names')
def tag_names():
    return stringify([dict(name=t, key=tag_sort_key(t)) for t in db.tag_names()])


@bottle.get('/tags')
def tags():
    req = bottle.request
    tags = tuple(t.strip() for t in req.query.tags.split('|') if t.strip())
    counts = collections.defaultdict(int)
    for m in db.find(tags=tags):
        for t in m.tag_set:
            counts[t] += 1
    return stringify(
        [dict(name=t, count=c, key=tag_sort_key(t), meta=tag_class(t))
         for t, c in counts.items()])


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
    if 'user_tags' in f:
        m.meta['user_tags'] = f['user_tags']
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
    post = lambda k: float(bottle.request.forms.get(k))
    db.find_one(id).add_op('ro', degrees=post('degrees'))
    return 'ok'

@bottle.post('/photos/<id:int>/contrast')
def contrast_photo(id):
    post = lambda k: float(bottle.request.forms.get(k))
    db.find_one(id).add_op('cb', gamma=post('gamma'), alpha=post('alpha'))
    return 'ok'

@bottle.post('/photos/<id:int>/crop')
def crop_photo(id):
    post = lambda k: float(bottle.request.forms.get(k))
    db.find_one(id).add_op('cr', box=[post(k) for k in 'x1 y1 x2 y2'.split()])
    return 'ok'

@bottle.post('/photos/<id:int>/equalize')
def equalize_photo(id):
    db.find_one(id).add_op('eq')
    return 'ok'


def main(args):
    bottle.run(host=args.host, port=args.port, reloader=args.reload)

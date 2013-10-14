import bottle
import collections
import hashlib
import lmj.cli
import lmj.photos
import os
import random
import sys

cmd = lmj.cli.add_command('serve')
cmd.add_argument('--host', default='localhost',
                 help='run server on this hostname')
cmd.add_argument('--port', type=int, default=5555, metavar='N',
                 help='run server on port N')
cmd.add_argument('--reload', action='store_true',
                 help='reload server whenever modules change')
cmd.set_defaults(mod=sys.modules[__name__])


STATIC = os.path.join(sys.prefix, 'share', 'lmj-photos', 'static')


@bottle.get('/')
def main():
    return static(os.path.join('views', 'main.html'))


@bottle.get('/static/<path:path>')
def static(path):
    for root in (os.path.dirname(lmj.photos.DB), os.curdir, 'static', STATIC):
        if os.path.isfile(os.path.join(root, path)):
            return bottle.static_file(path, root)


@bottle.get('/tags')
def tags():
    req = bottle.request

    groups = collections.defaultdict(set)
    metas = {}

    sql = 'SELECT id, meta, tags FROM photo WHERE 1=1'
    args = tuple(t.strip() for t in req.query.tags.split('|') if t.strip())
    if args:
        sql += ''.join(' AND tags LIKE ?' for t in args)
        args = tuple('%%|%s|%%' % t for t in args)

    with lmj.photos.connect() as db:
        for id, meta, tags in db.execute(sql, args):
            for t in tags.split('|'):
                if t.strip():
                    groups[t].add(id)
                    metas[id] = lmj.photos.parse(meta)

    result = []
    for tag, ids in groups.iteritems():
        photos = [dict(id=id, meta=metas[id], degrees=20 * random.random() - 10)
                  for _, id in zip(range(4), ids)]
        result.append(dict(name=tag, count=len(ids), photos=photos))
    return lmj.photos.stringify(result)


@bottle.get('/photo')
def photos():
    req = bottle.request
    tags = (t.strip() for t in req.query.tags.split('|') if t.strip())
    query = lmj.photos.find_many(offset=int(req.query.offset or 0),
                             limit=int(req.query.limit or 10),
                             tags=list(tags))
    return lmj.photos.stringify([p.to_dict() for p in query])


@bottle.post('/photo/<id:int>')
def post_photo(id):
    p = lmj.photos.find_one(id)
    f = lmj.photos.parse(list(bottle.request.forms)[0])
    if 'meta' in f:
        p.meta = f['meta']
        lmj.photos.update(p)
    return lmj.photos.stringify(p.to_dict())


@bottle.post('/photo/<id:int>/ro')
def rotate_photo(id):
    lmj.photos.find_one(id).add_op(
        'ro', degrees=float(bottle.request.forms.get('degrees')))
    return 'ok'

@bottle.post('/photo/<id:int>/cb')
def contrast_brightness_photo(id):
    post = lambda k: float(bottle.request.forms.get(k))
    lmj.photos.find_one(id).add_op(
        'cb', gamma=post('gamma'), alpha=post('alpha'))
    return 'ok'

@bottle.post('/photo/<id:int>/cr')
def crop_photo(id):
    post = lambda k: float(bottle.request.forms.get(k))
    lmj.photos.find_one(id).add_op(
        'cr', box=[post(k) for k in 'x1 y1 x2 y2'.split()])
    return 'ok'

@bottle.post('/photo/<id:int>/eq')
def equalize_photo(id):
    lmj.photos.find_one(id).add_op('eq')
    return 'ok'


@bottle.delete('/photo/<id:int>')
def delete_photo(id):
    pass


def main(args):
    bottle.run(host=args.host, port=args.port, reloader=args.reload)

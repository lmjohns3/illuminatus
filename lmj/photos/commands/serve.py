import bottle
import collections
import lmj.cli
import lmj.photos
import os
import sys

cmd = lmj.cli.add_command('serve')
cmd.add_argument('--host', default='localhost',
                 help='run server on this hostname')
cmd.add_argument('--port', type=int, default=5555, metavar='N',
                 help='run server on port N')
cmd.add_argument('--reload', action='store_true',
                 help='reload server whenever modules change')
cmd.add_argument('--thumbs', default=os.curdir, metavar='DIR',
                 help='load thumbnails from DIR')
cmd.set_defaults(mod=sys.modules[__name__])


WEB = os.path.join(sys.prefix, 'share', 'lmj-photos', 'web')
THUMBS = os.curdir


@bottle.get('/')
def main():
    return bottle.static_file('main.html', WEB)


@bottle.get('/static/<path:path>')
def static(path):
    if os.path.isfile(os.path.join(WEB, path)):
        return bottle.static_file(path, WEB)
    return bottle.static_file(path, THUMBS)


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
        photos = [dict(id=id, meta=metas[id]) for _, id in zip(range(4), ids)]
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
    sql = 'UPDATE photo SET tags = ?, meta = ?, stamp = ? where id = ?'
    data = '|%s|' % '|'.join(p.tag_set), lmj.photos.stringify(p.meta), p.stamp, id
    with lmj.photos.connect() as db:
        db.execute(sql, data)
        return lmj.photos.stringify(p.to_dict())

@bottle.post('/photo/<id:int>/rotate')
def rotate_photo(id):
    post = lambda k: bottle.request.forms.get(k)
    p = lmj.photos.find_one(id)
    p.rotate(float(post('degrees')))
    return 'ok'

@bottle.post('/photo/<id:int>/contrast-brightness')
def contrast_brightness_photo(id):
    post = lambda k: bottle.request.forms.get(k)
    p = lmj.photos.find_one(id)
    p.contrast_brightness(float(post('gamma')), float(post('alpha')))
    return 'ok'


def main(args):
    global THUMBS
    THUMBS = args.thumbs
    lmj.photos.DB = args.db
    bottle.run(host=args.host, port=args.port, reloader=args.reload)

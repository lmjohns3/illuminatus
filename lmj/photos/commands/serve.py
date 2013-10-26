import bottle
import collections
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
    for root in (os.path.dirname(lmj.photos.db.DB), os.curdir, 'static', STATIC):
        if os.path.isfile(os.path.join(root, path)):
            return bottle.static_file(path, root)


@bottle.get('/groups')
def groups():
    # build up some in-memory mappings from the database.
    tags = {}
    ids = collections.defaultdict(set)
    with lmj.photos.db.connect() as db:
        tags = dict(db.execute('SELECT id, name FROM tag'))
        for tid, pid in db.execute('SELECT tag_id, photo_id FROM photo_tag'):
            ids[tid].add(pid)

    # select a sample of photos from each tag group.
    selected = {}
    union = set()
    for tid, pids in ids.iteritems():
        s = random.sample(pids, 3) if len(pids) > 3 else list(pids)
        selected[tid] = s
        union |= set(s)
    union = tuple(union)

    # get metadata from the db for all selected photos.
    metas = {}
    with lmj.photos.db.connect() as db:
        for a in xrange(0, len(union), 512):
            unio = union[a:a+512]
            sql = ('SELECT id, meta FROM photo WHERE id IN (%s)' %
                   ','.join('?' for _ in unio))
            metas.update(dict(db.execute(sql, unio)))

    # assemble data for each group and send it over the wire.
    groups = []
    for tid, pids in ids.iteritems():
        groups.append(dict(
            name=tags[tid],
            count=len(pids),
            photos=[dict(thumb=lmj.photos.util.parse(metas[i])['thumb'],
                         degrees=20 * random.random() - 10)
                    for i in selected[tid]]))
    return lmj.photos.util.stringify(groups)


@bottle.get('/tags')
def tags():
    req = bottle.request
    tags = (t.strip() for t in req.query.tags.split('|') if t.strip())
    counts = collections.defaultdict(int)
    for p in lmj.photos.db.find_tagged(tuple(tags)):
        for t in p.tag_set:
            counts[t] += 1
    return lmj.photos.util.stringify(
        [dict(name=t, count=c) for t, c in counts.iteritems()])


@bottle.get('/photo')
def photos():
    req = bottle.request
    tags = (t.strip() for t in req.query.tags.split('|') if t.strip())
    return lmj.photos.util.stringify(
        [p.to_dict() for p in lmj.photos.db.find_tagged(
            tuple(tags),
            offset=int(req.query.offset or 0),
            limit=int(req.query.limit or 10))])


@bottle.post('/photo/<id:int>')
def post_photo(id):
    p = lmj.photos.db.find_one(id)
    f = lmj.photos.util.parse(list(bottle.request.forms)[0])
    if 'meta' in f:
        p.meta = f['meta']
        lmj.photos.db.update(p)
    return lmj.photos.util.stringify(p.to_dict())


@bottle.post('/photo/<id:int>/rotate')
def rotate_photo(id):
    lmj.photos.db.find_one(id).add_op(
        'ro', degrees=float(bottle.request.forms.get('degrees')))
    return 'ok'

@bottle.post('/photo/<id:int>/contrast')
def contrast_photo(id):
    post = lambda k: float(bottle.request.forms.get(k))
    lmj.photos.db.find_one(id).add_op(
        'cb', gamma=post('gamma'), alpha=post('alpha'))
    return 'ok'

@bottle.post('/photo/<id:int>/crop')
def crop_photo(id):
    post = lambda k: float(bottle.request.forms.get(k))
    lmj.photos.db.find_one(id).add_op(
        'cr', box=[post(k) for k in 'x1 y1 x2 y2'.split()])
    return 'ok'

@bottle.post('/photo/<id:int>/equalize')
def equalize_photo(id):
    lmj.photos.db.find_one(id).add_op('eq')
    return 'ok'


@bottle.delete('/photo/<id:int>')
def delete_photo(id):
    p = lmj.photos.db.find_one(id)
    key = None
    if bottle.request.forms.get('force'):
        key = p.path
    lmj.photos.delete(p.id, key)


def main(args):
    bottle.run(host=args.host, port=args.port, reloader=args.reload)

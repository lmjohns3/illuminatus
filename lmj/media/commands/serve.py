import bottle
import climate
import collections
import lmj.media
import os
import random
import sys

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


@bottle.get('/groups')
def groups():
    # build up some in-memory mappings from the database.
    tags = {}
    ids = collections.defaultdict(set)
    with lmj.media.db.connect() as db:
        tags = dict(db.execute('SELECT id, name FROM tag'))
        for tid, pid in db.execute('SELECT tag_id, media_id FROM media_tag'):
            ids[tid].add(pid)

    # select a sample of pieces from each tag group.
    selected = {}
    union = set()
    for tid, pids in ids.items():
        s = random.sample(pids, 3) if len(pids) > 3 else list(pids)
        selected[tid] = s
        union |= set(s)
    union = tuple(union)

    # get metadata from the db for all selected pieces.
    metas = {}
    with lmj.media.db.connect() as db:
        for a in range(0, len(union), 512):
            unio = union[a:a+512]
            sql = ('SELECT id, meta FROM media WHERE id IN (%s)' %
                   ','.join('?' for _ in unio))
            metas.update(dict(db.execute(sql, unio)))

    # assemble data for each group and send it over the wire.
    groups = []
    for tid, pids in ids.items():
        groups.append(dict(
            name=tags[tid],
            count=len(pids),
            pieces=[dict(thumb=lmj.media.util.parse(metas[i])['thumb'],
                         degrees=20 * random.random() - 10)
                    for i in selected[tid]]))
    return lmj.media.util.stringify(groups)


@bottle.get('/tags')
def tags():
    req = bottle.request
    tags = tuple(t.strip() for t in req.query.tags.split('|') if t.strip())
    if not tags:
        with lmj.media.db.connect() as db:
            return lmj.media.util.stringify(
                [t for _, t in db.execute('SELECT id, name FROM tag')])
    counts = collections.defaultdict(int)
    for p in lmj.media.db.find_tagged(tuple(tags)):
        for t in p.tag_set:
            counts[t] += 1
    return lmj.media.util.stringify(
        [dict(name=t, count=c) for t, c in counts.items()])


@bottle.get('/photo')
def photos():
    req = bottle.request
    tags = (t.strip() for t in req.query.tags.split('|') if t.strip())
    return lmj.media.util.stringify(
        [p.to_dict() for p in lmj.media.db.find_tagged(
            tuple(tags),
            offset=int(req.query.offset or 0),
            limit=int(req.query.limit or 10))])


@bottle.post('/photo/<id:int>')
def post_photo(id):
    p = lmj.media.db.find_one(id)
    f = lmj.media.util.parse(list(bottle.request.forms)[0])
    if 'meta' in f:
        p.meta = f['meta']
        lmj.media.db.update(p)
    return lmj.media.util.stringify(p.to_dict())


@bottle.post('/photo/<id:int>/rotate')
def rotate_photo(id):
    lmj.media.db.find_one(id).add_op(
        'ro', degrees=float(bottle.request.forms.get('degrees')))
    return 'ok'

@bottle.post('/photo/<id:int>/contrast')
def contrast_photo(id):
    post = lambda k: float(bottle.request.forms.get(k))
    lmj.media.db.find_one(id).add_op(
        'cb', gamma=post('gamma'), alpha=post('alpha'))
    return 'ok'

@bottle.post('/photo/<id:int>/crop')
def crop_photo(id):
    post = lambda k: float(bottle.request.forms.get(k))
    lmj.media.db.find_one(id).add_op(
        'cr', box=[post(k) for k in 'x1 y1 x2 y2'.split()])
    return 'ok'

@bottle.post('/photo/<id:int>/equalize')
def equalize_photo(id):
    lmj.media.db.find_one(id).add_op('eq')
    return 'ok'


@bottle.delete('/photo/<id:int>')
def delete_photo(id):
    p = lmj.media.db.find_one(id)
    lmj.media.db.delete(p.id, p.path)


def main(args):
    bottle.run(host=args.host, port=args.port, reloader=args.reload)

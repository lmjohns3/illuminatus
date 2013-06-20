#!/usr/bin/env python

import bottle
import collections
import datetime
import json
import cv
import os
import PIL.Image
import sqlite3
import subprocess
import sys


class connect(object):
    def __enter__(self):
        self.db = sqlite3.connect('photos.db', isolation_level=None)
        return self.db

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type or exc_value or traceback:
            print exc_type, exc_value, traceback
        self.db.close()


def parse(x):
    return json.loads(x)

def stringify(x):
    h = lambda z: z.isoformat() if isinstance(z, datetime.datetime) else None
    return json.dumps(x, default=h)


def import_all(root):
    def exists(p):
        with connect() as db:
            sql = 'SELECT COUNT(path) FROM photo WHERE path = ?'
            c, = db.execute(sql, (p, )).fetchone()
            return c > 0

    for base, dirs, files in os.walk(root):
        dots = [n for n in dirs if n.startswith('.')]
        [dirs.remove(d) for d in dots]
        for name in files:
            if name.startswith('.'): continue
            _, ext = os.path.splitext(name)
            if ext.lower()[1:] in 'gif jpg jpeg png':
                path = os.path.join(base, name)
                if exists(path):
                    print '=', path
                else:
                    import_one(path)
                    print '+', path

def import_one(path):
    exif, = parse(subprocess.check_output(['exiftool', '-json', path]))

    stamp = exif.get('DateTimeOriginal', exif.get('CreateDate'))
    if stamp:
        stamp = datetime.datetime.strptime(stamp[:19], '%Y:%m:%d %H:%M:%S')
    if not stamp:
        stamp = datetime.datetime.now()

    meta = dict(stamp=stamp, user_tags=[])

    photo = None
    with connect() as db:
        db.execute('INSERT INTO photo (path) VALUES (?)', (path, ))
        sql = 'SELECT id, path, meta, exif FROM photo WHERE path = ?'
        photo = Photo(*db.execute(sql, (path, )).fetchone())
        photo.meta = meta
        photo.exif = exif

    meta['thumb'] = photo.thumb_path

    # create the thumbnail files for this photo.
    img = PIL.Image.open(path)
    if exif.get('Orientation') == 'Rotate 90 CW':
        img = img.rotate(-90)
    if exif.get('Orientation') == 'Rotate 180':
        img = img.rotate(-180)
    if exif.get('Orientation') == 'Rotate 270 CW':
        img = img.rotate(-270)

    for name, size in (('thumb', 800), ('tiny', 120)):
        path = os.path.join(os.getcwd(), 'static', name, photo.thumb_path)
        dirname = os.path.dirname(path)
        try: os.makedirs(dirname)
        except: pass
        img.thumbnail((size, size), PIL.Image.ANTIALIAS)
        img.save(path)

    # update the database with correct metadata.
    with connect() as db:
        sql = 'UPDATE photo SET tags = ?, meta = ?, exif = ?, stamp = ? where id = ?'
        data = ('|%s|' % '|'.join(photo.tag_set),
                stringify(meta),
                stringify(exif),
                photo.stamp,
                photo.id)
        db.execute(sql, data)


class Photo(object):
    @classmethod
    def get(cls, id):
        sql = 'SELECT path, meta, exif FROM photo WHERE id = ?'
        with connect() as db:
            path, meta, exif = db.execute(sql, (id, )).fetchone()
            return cls(id, path, parse(meta), parse(exif))

    def __init__(self, id=-1, path='', meta=None, exif=None):
        self.id = id
        self.path = path
        self.meta = meta or {}
        self.exif = exif or {}

    @property
    def tag_set(self):
        return (self.datetime_tag_set |
                self.user_tag_set |
                self.geo_tag_set |
                self.exif_tag_set)

    @property
    def user_tag_set(self):
        return set(self.meta.get('user_tags', []))

    @property
    def geo_tag_set(self):
        return set()

    @property
    def datetime_tag_set(self):
        if not self.stamp:
            return set()

        def ordinal(n):
            s = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
            if 10 < n < 20: s = 'th'
            return '%d%s' % (n, s)

        return set([self.stamp.strftime('%Y'),
                    self.stamp.strftime('%B').lower(),
                    self.stamp.strftime('%A').lower(),
                    ordinal(int(self.stamp.strftime('%d'))),
                    self.stamp.strftime('%I%p').lower().strip('0'),
                    ])

    @property
    def exif_tag_set(self):
        return set()

    @property
    def stamp(self):
        stamp = self.meta.get('stamp')
        if not stamp:
            return None
        if isinstance(stamp, datetime.datetime):
            return stamp
        return datetime.datetime.strptime(stamp, '%Y-%m-%dT%H:%M:%S')

    @property
    def thumb_path(self):
        id = '%08x' % self.id
        return '%s/%s.jpg' % (id[:-3], id[-3:])

    def to_dict(self):
        return dict(id=self.id,
                    path=self.path,
                    stamp=self.stamp,
                    meta=self.meta,
                    exif=self.exif,
                    thumb=self.thumb_path,
                    tags=list(self.tag_set))


@bottle.get('/')
def main():
    return bottle.static_file(
        'main.html', os.path.join(os.getcwd(), 'static', 'views'))


@bottle.get('/static/<path:path>')
def static(path):
    return bottle.static_file(path, os.path.join(os.getcwd(), 'static'))


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

    with connect() as db:
        for id, meta, tags in db.execute(sql, args):
            for t in tags.split('|'):
                if t.strip():
                    groups[t].add(id)
                    metas[id] = parse(meta)

    result = []
    for tag, ids in groups.iteritems():
        photos = [dict(id=id, meta=metas[id]) for _, id in zip(range(4), ids)]
        result.append(dict(name=tag, count=len(ids), photos=photos))
    return stringify(result)


@bottle.get('/photo')
def photos():
    req = bottle.request

    sql = ('SELECT id, path, meta, exif FROM photo '
           'WHERE 1=1%s ORDER BY stamp DESC LIMIT ? OFFSET ?')

    offset = int(req.query.offset or 0)
    args = (int(req.query.limit or 10), offset)
    where = ''
    tags = [t.strip() for t in req.query.tags.split('|') if t.strip()]
    if tags:
        args = tuple('%%|%s|%%' % t for t in tags) + args
        where = ''.join(' AND tags LIKE ?' for t in tags)

    photos = []
    with connect() as db:
        for i, (id, path, meta, exif) in enumerate(db.execute(sql % where, args)):
            photos.append(Photo(id, path, parse(meta), parse(exif)).to_dict())

    return stringify(photos)


@bottle.get('/photo/<id:int>')
def get_photo(id):
    return stringify(Photo.get(id).to_dict())


@bottle.post('/photo/<id:int>')
def post_photo(id):
    p = Photo.get(id)
    f = parse(list(bottle.request.forms)[0])
    if 'meta' in f:
        p.meta = f['meta']
    sql = 'UPDATE photo SET tags = ?, meta = ?, stamp = ? where id = ?'
    data = '|%s|' % '|'.join(p.tag_set), stringify(p.meta), p.stamp, id
    with connect() as db:
        db.execute(sql, data)
        return stringify(p.to_dict())


if __name__ == '__main__':
    with connect() as db:
        try:
            db.execute('SELECT COUNT(*) FROM photo')
        except:
            db.execute("CREATE TABLE photo ("
                       "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                       "path VARCHAR UNIQUE NOT NULL DEFAULT '', "
                       "tags VARCHAR NOT NULL DEFAULT '||', "
                       "meta TEXT NOT NULL DEFAULT '{}', "
                       "exif TEXT NOT NULL DEFAULT '{}', "
                       "stamp DATETIME)")

    if len(sys.argv) > 1:
        for p in sys.argv[1:]:
            import_all(p)

    else:
        bottle.run(host='localhost', port=5555)


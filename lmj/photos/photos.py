import contextlib
import cv2
import datetime
import json
import lmj.cli
import os
import PIL.Image
import sqlite3
import subprocess

lmj.cli.add_arg('--db', default='photo.db', help='connect to this database')

DB = None

DEFAULT_SIZES = (('full', 1000), ('thumb', 200))

@contextlib.contextmanager
def connect():
    db = sqlite3.connect(DB, isolation_level=None)
    try:
        yield db
    finally:
        db.close()


def init():
    with connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS photo ("
                   "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                   "path VARCHAR UNIQUE NOT NULL DEFAULT '', "
                   "tags VARCHAR NOT NULL DEFAULT '||', "
                   "meta TEXT NOT NULL DEFAULT '{}', "
                   "exif TEXT NOT NULL DEFAULT '{}', "
                   "ops TEXT NOT NULL DEFAULT '[]', "
                   "stamp DATETIME)")


def parse(x):
    return json.loads(x)

def stringify(x):
    h = lambda z: z.isoformat() if isinstance(z, datetime.datetime) else None
    return json.dumps(x, default=h)


def find_one(id):
    sql = 'SELECT path, meta, exif, ops FROM photo WHERE id = ?'
    with connect() as db:
        path, meta, exif, ops = db.execute(sql, (id, )).fetchone()
        return Photo(id, path, parse(meta), parse(exif), parse(ops))


def find_many(offset=0, limit=10, tags=()):
    sql = ('SELECT id, path, meta, exif, ops FROM photo '
           'WHERE 1=1%s ORDER BY stamp DESC LIMIT ? OFFSET ?')

    args = (limit, offset)
    where = ''
    if tags:
        args = tuple('%%|%s|%%' % t for t in tags) + args
        where = ''.join(' AND tags LIKE ?' for t in tags)

    with connect() as db:
        for id, path, meta, exif, ops in db.execute(sql % where, args):
            yield Photo(id, path, parse(meta), parse(exif), parse(ops))


def exists(path):
    with connect() as db:
        sql = 'SELECT COUNT(path) FROM photo WHERE path = ?'
        c, = db.execute(sql, (path, )).fetchone()
        return c > 0


def import_(path):
    exif, = parse(subprocess.check_output(['exiftool', '-json', path]))

    stamp = datetime.datetime.now()
    for key in 'DateTimeOriginal CreateDate ModifyDate FileModifyDate'.split():
        stamp = exif.get(key)
        if stamp:
            stamp = datetime.datetime.strptime(stamp[:19], '%Y:%m:%d %H:%M:%S')
            break

    meta = dict(stamp=stamp, user_tags=[])

    photo = None
    with connect() as db:
        db.execute('INSERT INTO photo (path) VALUES (?)', (path, ))
        sql = 'SELECT id, path, meta, exif, ops FROM photo WHERE path = ?'
        photo = Photo(*db.execute(sql, (path, )).fetchone())
        photo.meta = meta
        photo.exif = exif

    photo.make_thumbnails(os.path.join(os.getcwd(), 'static', 'img'))
    photo.meta['thumb'] = photo.thumb_path

    # update the database with correct metadata.
    sql = 'UPDATE photo SET tags = ?, meta = ?, exif = ?, stamp = ? where id = ?'
    data = ('|%s|' % '|'.join(photo.tag_set),
            stringify(meta),
            stringify(exif),
            photo.stamp,
            photo.id)
    with connect() as db:
        db.execute(sql, data)


class Photo(object):
    def __init__(self, id=-1, path='', meta=None, exif=None, ops=None):
        self.id = id
        self.path = path
        self.meta = meta or {}
        self.exif = exif or {}
        self.ops = ops or []

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
        return os.path.join(id[:-3], '%s.jpg' % id[-3:])

    def to_dict(self):
        return dict(id=self.id,
                    path=self.path,
                    stamp=self.stamp,
                    meta=self.meta,
                    exif=self.exif,
                    ops=self.ops,
                    thumb=self.thumb_path,
                    tags=list(self.tag_set))

    def get_image(self):
        img = PIL.Image.open(self.path)
        if self.exif.get('Orientation') == 'Rotate 90 CW':
            img = img.rotate(-90)
        if self.exif.get('Orientation') == 'Rotate 180':
            img = img.rotate(-180)
        if self.exif.get('Orientation') == 'Rotate 270 CW':
            img = img.rotate(-270)

        for op in self.ops:
            key = op['type']
            if key == 'equalize_histogram':
                # http://opencvpython.blogspot.com/2013/03/histograms-2-histogram-equalization.html
                img = cv2.equalizeHist(img)
                continue
            if key == 'crop':
                x1, y1, x2, y2 = op['box']
                width, height = img.size
                x1 *= width
                y1 *= height
                x2 *= width
                y2 *= height
                img = img.crop([x1, y1, x2, y2])
                continue
            if key == 'rotate':
                img = img.rotate(op['degrees'])
                continue
            # TODO: apply more image transforms

        return img

    def make_thumbnails(self, path, sizes=DEFAULT_SIZES, replace=False):
        img = self.get_image()
        for name, size in sorted(sizes, key=lambda x: -x[1]):
            p = os.path.join(path, name, self.thumb_path)
            if replace or not os.path.exists(p):
                dirname = os.path.dirname(p)
                try: os.makedirs(dirname)
                except: pass
                img.thumbnail((size, size), PIL.Image.ANTIALIAS)
                img.save(p)

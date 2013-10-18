import contextlib
import hashlib
import sqlite3

from . import colorspace

from .photos import Photo, parse, stringify


@contextlib.contextmanager
def connect():
    db = sqlite3.connect(DB, isolation_level=None)
    try:
        yield db
    finally:
        db.close()


DB = 'photos.db'

def init(path):
    global DB
    DB = path
    with connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS photo ("
                   "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                   "path VARCHAR UNIQUE NOT NULL DEFAULT '', "
                   "tags VARCHAR NOT NULL DEFAULT '||', "
                   "meta TEXT NOT NULL DEFAULT '{}', "
                   "ops TEXT NOT NULL DEFAULT '[]', "
                   "stamp DATETIME)")


def find_one(id):
    '''Find a single photo by its id.'''
    sql = 'SELECT path, meta, ops FROM photo WHERE id = ?'
    with connect() as db:
        return Photo(id, *db.execute(sql, (id, )).fetchone())


def find_many(offset=0, limit=10, tags=()):
    '''Find photos matching a particular tag set.'''
    sql = ('SELECT id, path, meta, ops FROM photo '
           'WHERE 1=1%s ORDER BY stamp DESC LIMIT ? OFFSET ?')
    args = (limit, offset)
    where = ''
    if tags:
        args = tuple('%%|%s|%%' % t for t in tags) + args
        where = ''.join(' AND tags LIKE ?' for t in tags)
    with connect() as db:
        for row in db.execute(sql % where, args):
            yield Photo(*row)


def exists(path):
    '''Check whether a given photo exists in the database.'''
    with connect() as db:
        sql = 'SELECT COUNT(path) FROM photo WHERE path = ?'
        c, = db.execute(sql, (path, )).fetchone()
        return c > 0


def insert(path):
    '''Add a new photo to the database.'''
    with connect() as db:
        db.execute('INSERT INTO photo (path) VALUES (?)', (path, ))
        sql = 'SELECT id, path, meta, ops FROM photo WHERE path = ?'
        return Photo(*db.execute(sql, (path, )).fetchone())


def update(photo):
    '''Update the database with correct metadata.'''
    sql = ('UPDATE photo '
           'SET tags = ?, meta = ?, ops = ?, stamp = ? '
           'WHERE id = ?')
    data = ('|%s|' % '|'.join(photo.tag_set),
            stringify(photo.meta),
            stringify(photo.ops),
            photo.stamp,
            photo.id)
    with connect() as db:
        db.execute(sql, data)


def delete(path, remove_if_md5_matches=None):
    '''Remove a photo.

    WARNING: Also removes the original source file from disk, if
    remove_if_md5_matches contains the md5 digest of the given path.
    '''
    with connect() as db:
        db.execute('DELETE FROM photo WHERE path = ?', (path, ))
    if remove_if_md5_matches == hashlib.md5(path).digest():
        os.unlink(path)

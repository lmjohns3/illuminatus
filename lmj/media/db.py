import contextlib
import lmj.cli
import os
import sqlite3

from .photos import Photo
from .util import stringify

logging = lmj.cli.get_logger('lmj.media')

DB = 'photos.db'

@contextlib.contextmanager
def connect():
    db = sqlite3.connect(DB)
    db.execute('PRAGMA foreign_keys = ON')
    try:
        yield db
        db.commit()
    finally:
        db.close()


def init(path):
    global DB
    DB = path
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS photo '
                   '( id INTEGER PRIMARY KEY AUTOINCREMENT'
                   ", path VARCHAR UNIQUE NOT NULL DEFAULT ''"
                   ", meta TEXT NOT NULL DEFAULT '{}'"
                   ", ops TEXT NOT NULL DEFAULT '[]'"
                   ', stamp DATETIME'
                   ')')
        db.execute('CREATE TABLE IF NOT EXISTS tag '
                   '( id INTEGER PRIMARY KEY AUTOINCREMENT'
                   ", name VARCHAR UNIQUE NOT NULL DEFAULT ''"
                   ')')
        db.execute('CREATE TABLE IF NOT EXISTS photo_tag'
                   '( photo_id INTEGER NOT NULL DEFAULT 0'
                   ', tag_id INTEGER NOT NULL DEFAULT 0'
                   ', FOREIGN KEY(photo_id) REFERENCES photo(id)'
                   ', FOREIGN KEY(tag_id) REFERENCES tag(id)'
                   ')')
        db.execute('CREATE UNIQUE INDEX IF NOT EXISTS pt_photo_tag '
                   'ON photo_tag(photo_id, tag_id)')
        db.execute('CREATE INDEX IF NOT EXISTS pt_photo '
                   'ON photo_tag(photo_id)')
        db.execute('CREATE INDEX IF NOT EXISTS pt_tag '
                   'ON photo_tag(tag_id)')


def find_one(id):
    '''Find a single photo by its id.'''
    sql = 'SELECT path, meta, ops FROM photo WHERE id = ?'
    with connect() as db:
        return Photo(id, *db.execute(sql, (id, )).fetchone())


def find_tagged(tags, offset=0, limit=999999999):
    '''Find photos matching all given tags.'''
    if not tags:
        return
    sql = ('SELECT p.id, p.path, p.meta, p.ops FROM %s WHERE %s '
           'ORDER BY stamp DESC LIMIT ? OFFSET ?')
    tables = ['photo AS p']
    wheres = []
    for i, t in enumerate(tags):
        tables.extend(['photo_tag AS pt%d' % i, 'tag AS t%d' % i])
        wheres.extend(['p.id = pt%d.photo_id' % i,
                       't%d.id = pt%d.tag_id' % (i, i),
                       't%d.name = ?' % i])
    with connect() as db:
        sql = sql % (', '.join(tables), ' AND '.join(wheres))
        for row in db.execute(sql, tuple(tags) + (limit, offset)):
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
        sql = 'SELECT id, path FROM photo WHERE path = ?'
        return Photo(*db.execute(sql, (path, )).fetchone())


def update(photo):
    '''Update the database with new photo metadata.'''
    with connect() as db:
        # update photo information in database.
        db.execute('UPDATE photo SET meta = ?, ops = ?, stamp = ? WHERE id = ?', (
            stringify(photo.meta), stringify(photo.ops), photo.stamp, photo.id))

        # get current tags for photo.
        tag_tuple = tuple(photo.tag_set)
        jc = lambda x, n=len(tag_tuple): ('{},'.format(x) * n)[:-1]

        # of the current tags, find the ones that already exist in the database,
        # and insert any that are missing. get the ids for matching tags.
        sql = 'SELECT name, id FROM tag WHERE name IN (%s)' % jc('?')
        existing = set([t for t, _ in db.execute(sql, tag_tuple)])
        m = tuple(set(tag_tuple) - existing)
        if m:
            db.execute('INSERT INTO tag (name) VALUES %s' % jc('(?)', len(m)), m)
        ids = tuple(i for _, i in db.execute(sql, tag_tuple))

        # remove existing tag associations.
        db.execute('DELETE FROM photo_tag WHERE photo_id = ?', (photo.id, ))

        # re-insert tag associations for current tags.
        sql = 'INSERT INTO photo_tag (photo_id, tag_id) VALUES %s' % jc('(?,?)')
        data = []
        for i in ids:
            data.extend((photo.id, i))
        db.execute(sql, tuple(data))


def delete(id, hide_original_if_path_matches=None):
    '''Remove a photo.

    WARNING: If hide_original_if_path_matches contains the path for the photo,
    the original file will be renamed with a hidden (dot) prefix.
    '''
    photo = find_one(id)

    # remove thumbnails of this photo.
    base = os.path.dirname(DB)
    for size in os.listdir(base):
        try:
            os.unlink(os.path.join(base, size, photo.thumb_path))
        except:
            pass

    # if desired, hide the original file referenced by this photo.
    if hide_original_if_path_matches == photo.path:
        dirname = os.path.dirname(photo.path)
        basename = os.path.basename(photo.path)
        try:
            os.rename(photo.path, os.path.join(dirname, '.lmj-removed-' + basename))
        except:
            logging.exception('%s: error renaming photo', photo.path)

    # remove photo from the database.
    with connect() as db:
        db.execute('DELETE FROM photo_tag WHERE photo_id = ?', (id, ))
        db.execute('DELETE FROM photo WHERE id = ?', (id, ))


def remove_path(path):
    '''Remove a photo by path.'''
    with connect() as db:
        db.execute('DELETE FROM photo WHERE path = ?', (path, ))

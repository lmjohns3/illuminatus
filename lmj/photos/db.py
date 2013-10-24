import contextlib
import lmj.cli
import sqlite3

from .photos import Photo
from .util import stringify

logging = lmj.cli.get_logger('lmj.photos')

DB = 'photos.db'
ENABLE_DELETE_ORIGINAL = False

@contextlib.contextmanager
def connect():
    db = sqlite3.connect(DB)
    db.execute('PRAGMA foreign_keys = ON')
    try:
        yield db
        db.commit()
    finally:
        db.close()


def init(path, enable_delete_original=False):
    global DB, ENABLE_DELETE_ORIGINAL
    DB = path
    ENABLE_DELETE_ORIGINAL = enable_delete_original
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


def delete(id, remove_if_path_matches=None):
    '''Remove a photo.

    WARNING: Also removes the original source file from disk, if
    remove_if_path_matches contains the path for the photo, and the module-level
    flag ENABLE_DELETE_ORIGINAL has been set.
    '''
    photo = find_one(id)

    # remove thumbnails of this photo.
    base = os.path.dirname(DB)
    for size in os.listdir(base):
        try:
            os.unlink(os.path.join(base, size, photo.thumb_path))
        except:
            pass

    # if desired, remove the original file referenced by this photo.
    if remove_if_path_matches == photo.path and ENABLE_DELETE_ORIGINAL:
        try:
            os.unlink(photo.path)
        except:
            logging.exception('%s: error removing photo', photo.path)

    # remove photo from the database.
    with connect() as db:
        db.execute('DELETE FROM photo_tag WHERE photo_id = ?', (id, ))
        db.execute('DELETE FROM photo WHERE id = ?', (id, ))


def clean(path):
    '''Remove a photo by path.'''
    with connect() as db:
        db.execute('DELETE FROM photo WHERE path = ?', (path, ))

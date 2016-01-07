import climate
import contextlib
import os
import re
import sqlite3

from .util import stringify

logging = climate.get_logger(__name__)

DB = 'media.db'

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
        db.execute('CREATE TABLE IF NOT EXISTS media '
                   '( id INTEGER PRIMARY KEY AUTOINCREMENT'
                   ', medium INTEGER NOT NULL DEFAULT 0'
                   ", path VARCHAR UNIQUE NOT NULL DEFAULT ''"
                   ", meta BLOB NOT NULL DEFAULT '{}'"
                   ', stamp DATETIME'
                   ')')
        db.execute('CREATE TABLE IF NOT EXISTS tag '
                   '( id INTEGER PRIMARY KEY AUTOINCREMENT'
                   ", name VARCHAR UNIQUE NOT NULL DEFAULT ''"
                   ')')
        db.execute('CREATE TABLE IF NOT EXISTS media_tag'
                   '( media_id INTEGER NOT NULL DEFAULT 0'
                   ', tag_id INTEGER NOT NULL DEFAULT 0'
                   ', FOREIGN KEY(media_id) REFERENCES media(id)'
                   ', FOREIGN KEY(tag_id) REFERENCES tag(id)'
                   ')')
        db.execute('CREATE UNIQUE INDEX IF NOT EXISTS mt_media_tag '
                   'ON media_tag(media_id, tag_id)')
        db.execute('CREATE INDEX IF NOT EXISTS pt_media '
                   'ON media_tag(media_id)')
        db.execute('CREATE INDEX IF NOT EXISTS pt_tag '
                   'ON media_tag(tag_id)')

    # clean up unused tags.
    with connect() as db:
        used_ids = set(i for i, in db.execute('SELECT DISTINCT tag_id FROM media_tag'))
        all_ids = set(i for i, in db.execute('SELECT id FROM tag'))
        unused_ids = tuple(all_ids - used_ids)
        if unused_ids:
            logging.info('cleaning up %d unused tags', len(unused_ids))
            db.execute('DELETE FROM tag WHERE id IN (%s)' %
                       ','.join('?' for _ in unused_ids), unused_ids)


def media_classes():
    from .photos import Photo
    from .videos import Video
    return (Photo, Video)


def build_media(id, medium, path, meta=None):
    '''Build an object of the appropriate class given the medium and data.'''
    for cls in media_classes():
        if medium == cls.MEDIUM:
            return cls(id, path, meta)
    raise ValueError('unknown medium {}'.format(medium))


def tag_names():
    '''Get a list of all tag names in the database.'''
    with connect() as db:
        return [t for t, in db.execute('SELECT name FROM tag')]


def find_one(id):
    '''Find a single media piece by its id.'''
    sql = 'SELECT medium, path, meta FROM media WHERE id = ?'
    with connect() as db:
        medium, path, meta = db.execute(sql, (id, )).fetchone()
        return build_media(id, medium, path, meta)


def find(path='', ids=(), tags=(), before=None, after=None, offset=0, limit=1 << 31):
    '''Find multiple media pieces.'''
    sql = ('SELECT m.id, m.medium, m.path, m.meta '
           'FROM {tables} WHERE {wheres} '
           'ORDER BY stamp DESC LIMIT ? OFFSET ?')
    args = []
    tables = ['media AS m']
    wheres = ['1 = 1']
    if before:
        wheres.append('stamp < ?')
        args.append(before)
    if after:
        wheres.append('stamp > ?')
        args.append(after)
    if ids:
        wheres.append('id IN ({})'.format(','.join('?' for _ in ids)))
        args.extend(ids)
    if path:
        wheres.append('path LIKE ?')
        args.append(re.sub(r'\*|\[[^\]]+\]', '%', path))
    for i, t in enumerate(tags):
        tables.extend(['media_tag AS mt{}'.format(i), 'tag AS t{}'.format(i)])
        wheres.extend([
            'm.id = mt{}.media_id'.format(i),
            't{}.id = mt{}.tag_id'.format(i, i),
            't{}.name LIKE ?'.format(i),
        ])
        args.append(re.sub(r'\*|\[[^\]]+\]', '%', t))
    sql = sql.format(tables=', '.join(tables), wheres=' AND '.join(wheres))
    with connect() as db:
        for row in db.execute(sql, tuple(args) + (limit, offset)):
            yield build_media(*row)


def exists(path):
    '''Check whether a given piece exists in the database.'''
    with connect() as db:
        sql = 'SELECT COUNT(path) FROM media WHERE path = ?'
        for c, in db.execute(sql, (path, )):
            return c > 0


def insert(path, medium):
    '''Add a new piece to the database.'''
    with connect() as db:
        sql = 'INSERT INTO media (path, medium) VALUES (?, ?)'
        db.execute(sql, (path, medium))
        sql = 'SELECT id, medium, path FROM media WHERE path = ?'
        return build_media(*db.execute(sql, (path, )).fetchone())


def update(piece):
    '''Update the database with new metadata.'''
    with connect() as db:
        # update metadata in database.
        db.execute('UPDATE media SET meta = ?, stamp = ? WHERE id = ?', (
            stringify(piece.meta), piece.stamp, piece.id))

        # get current tags for piece.
        tag_tuple = tuple(piece.tag_set)
        jc = lambda x, n=len(tag_tuple): ('{},'.format(x) * n)[:-1]

        # of the current tags, find the ones that already exist in the database,
        # and insert any that are missing. get the ids for matching tags.
        sql = 'SELECT name, id FROM tag WHERE name IN (%s)' % jc('?')
        existing = set(t for t, _ in db.execute(sql, tag_tuple))
        m = tuple(set(tag_tuple) - existing)
        if m:
            db.execute('INSERT INTO tag (name) VALUES %s' % jc('(?)', len(m)), m)
        ids = set(i for _, i in db.execute(sql, tag_tuple))

        # remove existing tag associations.
        db.execute('DELETE FROM media_tag WHERE media_id = ?', (piece.id, ))

        # re-insert tag associations for current tags.
        sql = 'INSERT INTO media_tag (media_id, tag_id) VALUES %s' % jc('(?,?)')
        data = []
        for i in ids:
            data.extend((piece.id, i))
        db.execute(sql, tuple(data))


def delete(id, hide_original_if_path_matches=None):
    '''Remove a piece of media.

    WARNING: If hide_original_if_path_matches contains the path for the photo,
    the original file will be renamed with a hidden (dot) prefix.
    '''
    piece = find_one(id)
    piece.cleanup()

    # if desired, hide the original file referenced by this photo.
    if hide_original_if_path_matches == piece.path:
        dirname = os.path.dirname(piece.path)
        basename = os.path.basename(piece.path)
        try:
            os.rename(piece.path, os.path.join(
                dirname, '.illuminatus-removed-' + basename))
        except:
            logging.exception('%s: error renaming source', piece.path)

    # remove photo from the database.
    with connect() as db:
        db.execute('DELETE FROM media_tag WHERE media_id = ?', (id, ))
        db.execute('DELETE FROM media WHERE id = ?', (id, ))


def remove_path(path):
    '''Remove a media piece by path.'''
    with connect() as db:
        db.execute('DELETE FROM media WHERE path = ?', (path, ))

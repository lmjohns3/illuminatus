import click
import collections
import contextlib
import fnmatch
import logging
import mimetypes
import os
import parsimonious.grammar
import sqlite3
import ujson

from .media import Media, Tag


def _subclasses(base):
    '''Recursively yield all known subclasses of the given base class.'''
    for cls in base.__subclasses__():
        yield from _subclasses(cls)
        yield cls


def _fetchone(cur, sql, *args):
    return cur.execute(sql, args).fetchone()


def _fetchall(cur, sql, *args, n=999):
    if not args:
        return cur.execute(sql).fetchall()
    rows = []
    for i in range(0, len(args), n):
        chunk = args[i:i+n]
        marks = ','.join('?' * len(chunk))
        rows.extend(cur.execute(sql.format(marks), chunk).fetchall())
    return rows


def _get_id_by_path(cur, path):
    return _fetchone(cur, 'SELECT id FROM media WHERE path = ?', path)


def _create(cur, rec):
    cur.execute('INSERT INTO media (path, medium, meta) VALUES (?, ?, ?)',
                (rec['path'], rec['medium'], ''))
    _update(cur, _get_id_by_path(cur, rec['path'])[0], rec)


def _update(cur, media_id, rec, *index):
    rec['id'] = media_id
    cur.execute('UPDATE media SET meta = ? WHERE id = ?',
                (ujson.dumps(rec, ensure_ascii=False), media_id))
    for field in index:
        if field in rec:
            cur.execute('UPDATE media SET {} = ? WHERE id = ?'.format(field),
                        (rec[field], media_id))


def _delete(cur, path):
    media_id = _get_id_by_path(cur, path)
    if media_id is not None:
        media_id, = media_id
        _clear_tags(cur, media_id)
        cur.execute('DELETE FROM media WHERE id = ?', (media_id,))


def _clear_tags(cur, media_id):
    cur.execute('DELETE FROM taggedmedia WHERE media_id = ?', (media_id, ))


def _add_tag(cur, media_id, tag):
    get = 'SELECT id FROM tags WHERE name = ? AND source = ?'
    found = _fetchone(cur, get, tag['name'], tag['source'])
    if found is None:
        cur.execute('INSERT INTO tags (name, source, sort) VALUES (?, ?, ?)',
                    (tag['name'], tag['source'], tag['sort']))
        found = _fetchone(cur, get, tag['name'], tag['source'])
    cur.execute('INSERT INTO taggedmedia (tag_id, media_id) VALUES (?, ?)',
                (found[0], media_id))


_SCHEMA = '''\
CREATE TABLE IF NOT EXISTS media (
  id INTEGER PRIMARY KEY NOT NULL,
  path TEXT UNIQUE NOT NULL,
  medium TEXT NOT NULL,
  stamp TEXT,
  fingerprint TEXT,
  meta BLOB NOT NULL);

CREATE INDEX IF NOT EXISTS idx_media_medium ON media(medium);
CREATE INDEX IF NOT EXISTS idx_media_stamp ON media(stamp);
CREATE INDEX IF NOT EXISTS idx_media_fingerprint ON media(fingerprint);

CREATE TABLE IF NOT EXISTS tags (
  id INTEGER PRIMARY KEY NOT NULL,
  name TEXT NOT NULL,
  source INTEGER NOT NULL DEFAULT 0,
  sort INTEGER NOT NULL DEFAULT 0);

CREATE INDEX IF NOT EXISTS idx_tags_name ON tags(name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tags_name_source ON tags(name, source);

CREATE TABLE IF NOT EXISTS taggedmedia (
  id INTEGER PRIMARY KEY NOT NULL,
  media_id INTEGER REFERENCES media(id),
  tag_id INTEGER REFERENCES tags(id));

CREATE INDEX IF NOT EXISTS idx_taggedmedia_media_id ON taggedmedia(media_id);
CREATE INDEX IF NOT EXISTS idx_taggedmedia_tag_id ON taggedmedia(tag_id);
'''


class QueryParser(parsimonious.NodeVisitor):
    '''Media can be queried using a special query syntax; we parse it here.

    The query syntax permits the following atoms, each of which represents a
    set of media items in the database:

    - after:S -- selects media with timestamps greater than or equal to S
    - before:S -- selects media with timestamps less than or equal to S
    - path:S -- selects media with S in their paths
    - id:S -- selects media item with database id S
    - S -- selects media tagged with S

    The specified sets can be combined using any combination of:

    - x | y -- contains media in either set x or set y
    - x & y -- contains media in both sets x and y
    - x ~ y -- contains media in set x but not set y

    Any of the operators above can be combined multiple times, and parentheses
    can be used to group sets together. For example, a & b ~ c selects media
    matching both a and b, but not c, while a & (b ~ c) matches both a and d,
    where d consists of things in b but not c.
    '''

    grammar = parsimonious.Grammar('''\
    query      = (union / group)+
    union      = intersect runion*
    runion     = _ '|' _ intersect
    intersect  = diff rintersect*
    rintersect = _ '&' _ diff
    diff       = set rdiff*
    rdiff      = _ '~' _ set
    set        = stamp / path / id / tag / group
    stamp      = ~r'(before|after):\S+'
    path       = ~r'path:\S+'
    id         = ~r'id:\d+'
    tag        = ~r'\w+([- ]\w+)*'
    group      = '(' _ query _ ')'
    _          = ~r'\s*'
    ''')

    def __init__(self):
        self.tags = set()
        self.stamps = set()
        self.paths = set()
        self.ids = set()

        self.ops = []

        self._intersect = []
        self._union = []
        self._diff = []

    def compute(self, media_ids_by_tag_name):
        return self.ops[0](media_ids_by_tag_name)

    def generic_visit(self, node, visited_children):
        pass

    def visit_union(self, node, visited_children):
        sets = [self.ops.pop(-1)] + self._union
        self.ops.append(
            lambda ids: set.union(*tuple(s(ids) for s in sets)))
        self._union = []

    def visit_runion(self, node, visited_children):
        self._union.append(self.ops.pop(-1))

    def visit_intersect(self, node, visited_children):
        sets = [self.ops.pop(-1)] + self._intersect
        self.ops.append(
            lambda ids: set.intersection(*tuple(s(ids) for s in sets)))
        self._intersect = []

    def visit_rintersect(self, node, visited_children):
        self._intersect.append(self.ops.pop(-1))

    def visit_diff(self, node, visited_children):
        sets = [self.ops.pop(-1)] + self._diff
        self.ops.append(
            lambda ids: set.difference(*tuple(s(ids) for s in sets)))
        self._diff = []

    def visit_rdiff(self, node, visited_children):
        self._diff.append(self.ops.pop(-1))

    def visit_tag(self, node, visited_children):
        self.tags.add(node.text)
        self.ops.append(lambda ids: ids[node.text])

    def visit_stamp(self, node, visited_children):
        self.stamps.add(node.text)
        self.ops.append(lambda ids: ids[node.text])

    def visit_path(self, node, visited_children):
        self.paths.add(node.text)
        self.ops.append(lambda ids: ids[node.text])

    def visit_id(self, node, visited_children):
        self.ids.add(node.text)
        self.ops.append(lambda ids: ids[node.text])


class _DebugCursor:
    def __init__(self, cur):
        self.cur = cur

    def execute(self, sql, args=()):
        click.echo('{} {}'.format(
            click.style(sql, fg='cyan'),
            click.style(str(args), fg='yellow')))
        return self.cur.execute(sql, args)


class DB(object):
    '''A database for storing media metadata.'''

    def __init__(self, path):
        self.path = os.path.abspath(os.path.expanduser(path))
        self.root = os.path.dirname(self.path)

    @property
    def tags(self):
        '''All tags in the database.'''
        sql = 'SELECT name, source, sort FROM tags ORDER BY source, sort, name'
        with self._cursor() as cur:
            return [Tag(*row) for row in cur.execute(sql).fetchall()]

    @contextlib.contextmanager
    def _cursor(self):
        cur = sqlite3.connect(self.path)
        cur.execute('PRAGMA encoding = "UTF-8"')
        cur.execute('PRAGMA foreign_keys = ON')
        cur.execute('PRAGMA journal_mode = WAL')
        cur.execute('PRAGMA synchronous = NORMAL')
        with cur:
            yield cur  # _DebugCursor(cur)
        cur.close()

    def setup(self):
        '''Set up the database schema.'''
        with self._cursor() as cur:
            for sql in _SCHEMA.split(';'):
                if sql.strip():
                    cur.execute(sql.strip())

    def create(self, path):
        '''Build an object for representing the given path.

        Parameters
        ----------
        path : str
            Filesystem path where the media item is stored.

        Returns
        -------
        item : `illuminatus.base.Media`
            A media item. Returns None if no known media types handle the given
            path.
        '''
        mime, _ = mimetypes.guess_type(path)
        for cls in _subclasses(Media):
            for pattern in cls.MIME_TYPES:
                if fnmatch.fnmatch(mime, pattern):
                    rec = dict(path=path, medium=cls.__name__.lower())
                    with self._cursor() as cur:
                        _create(cur, rec)
                    return cls(self, rec)
        return None

    def select_by_id(self, *ids, order='stamp-', offset=0, limit=0):
        '''Find one or more media pieces by database id.

        Parameters
        ----------
        ids : int
            Get items from the database corresponding to these ids.
        order : str, optional
            Record field to use for sorting. Defaults to 'stamp-' (i.e., most
            recent first). Add a '-' after the field name to sort descending.
        offset : int, optional
            Return records starting at this offset. Defaults to 0.
        limit : int, optional
            Return only this many records. Defaults to all records.
        '''
        if not ids:
            return []

        reverse = False
        if order.endswith('-'):
            reverse = True
            order = order[:-1]

        with self._cursor() as cur:
            recs = _fetchall(cur, 'SELECT meta FROM media WHERE id IN ({})', *ids)
        ordered = sorted((ujson.loads(rec) for rec, in recs),
                         key=lambda rec: rec.get(order, ''), reverse=reverse)

        def build(rec):
            for cls in _subclasses(Media):
                if rec.get('medium', '').lower() == cls.__name__.lower():
                    return cls(self, rec)
            raise ValueError('unknown medium for record {}'.format(rec))

        limit = limit or len(ordered)
        return [build(rec) for rec in ordered[offset:offset + limit]]

    def select_by_path(self, *paths, order='stamp-', offset=0, limit=0):
        '''Find one or more media pieces by path.

        Parameters
        ----------
        paths : str
            Get items from the database corresponding to these paths.
        order : str, optional
            Record field to use for sorting. Defaults to 'stamp-' (i.e., most
            recent first). Add a '-' after the field name to sort descending.
        offset : int, optional
            Return records starting at this offset. Defaults to 0.
        limit : int, optional
            Return only this many records. Defaults to all records.
        '''
        if not paths:
            return []
        with self._cursor() as cur:
            ids = _fetchall(cur, 'SELECT id FROM media WHERE path IN ({})', *paths)
            return self.select_by_id(*tuple(i for i, in ids),
                                     order=order, offset=offset, limit=limit)

    def select_by_fingerprint(self, *fps, order='stamp-', offset=0, limit=0):
        '''Find one or more media pieces by path.

        Parameters
        ----------
        fps : str
            Get items from the database corresponding to these fingerprints.
        order : str, optional
            Record field to use for sorting. Defaults to 'stamp-' (i.e., most
            recent first). Add a '-' after the field name to sort descending.
        offset : int, optional
            Return records starting at this offset. Defaults to 0.
        limit : int, optional
            Return only this many records. Defaults to all records.
        '''
        if not fps:
            return []
        with self._cursor() as cur:
            sql = 'SELECT id FROM media WHERE fingerprint IN ({})'
            ids = _fetchall(cur, sql, *fps)
            return self.select_by_id(*tuple(i for i, in ids),
                                     order=order, offset=offset, limit=limit)

    def select(self, query, order='stamp-', offset=0, limit=0):
        '''Find one or more media pieces by parsing a query.

        Parameters
        ----------
        query : str
            Get items from the database matching this query.
        order : str, optional
            Record field to use for sorting. Defaults to 'stamp-'.
            Add a '-' after the field name to sort descending.
        offset : int, optional
            Return records starting at this offset. Defaults to 0.
        limit : int, optional
            Return only this many records. Defaults to all records.
        '''
        if not query.strip():
            with self._cursor() as cur:
                media_ids = _fetchall(cur, 'SELECT id FROM media')
            return self.select_by_id(*tuple(i for i, in media_ids),
                                     order=order, offset=offset, limit=limit)

        parser = QueryParser()
        parser.parse(query)

        t_sql = 'SELECT id, name FROM tags WHERE name IN ({})'
        tm_sql = 'SELECT tag_id, media_id FROM taggedmedia WHERE tag_id IN ({})'
        s_sql = 'SELECT id FROM media WHERE stamp %s= {}'
        p_sql = 'SELECT id FROM media WHERE path LIKE ?'

        media_sets = collections.defaultdict(set)
        with self._cursor() as cur:
            if parser.tags:
                names = dict(_fetchall(cur, t_sql, *tuple(parser.tags)))
                if names:
                    for tag_id, media_id in _fetchall(cur, tm_sql, *tuple(names)):
                        media_sets[names[tag_id]].add(media_id)

            for stamp in parser.stamps:
                direction, query = stamp.split(':', 1)
                media_sets[stamp].update(i for i, in _fetchall(
                    cur, s_sql % '><'[direction == 'before'], query))

            for path in parser.paths:
                media_sets[path].update(i for i, in _fetchall(
                    cur, p_sql, '%{}%'.format(path.split(':', 1)[1])))

            for id in parser.ids:
                # create a set containing just the one numeric id
                media_sets[id].add(int(id.split(':')[1]))

        media_ids = parser.compute(media_sets)
        if not media_ids:
            return []

        return self.select_by_id(*tuple(media_ids),
                                 order=order, offset=offset, limit=limit)

    def exists(self, path):
        '''Check whether a given path exists in the database.'''
        with self._cursor() as cur:
            return _get_id_by_path(cur, path) is not None

    def update(self, rec):
        '''Update a media item in the database.

        Parameters
        ----------
        rec : dict
            A record of media metadata. The "path" value in this record will be
            used as a key for database operations.
        '''
        with self._cursor() as cur:
            media_id, = _get_id_by_path(cur, rec['path'])
            _update(cur, media_id, rec, 'stamp', 'fingerprint')
            _clear_tags(cur, media_id)
            for tag in rec['tags']:
                _add_tag(cur, media_id, tag)

    def delete(self, path):
        '''Remove a piece of media.

        Parameters
        ----------
        path : str
            Path of the media item to remove.
        '''
        with self._cursor() as cur:
            _delete(cur, path)

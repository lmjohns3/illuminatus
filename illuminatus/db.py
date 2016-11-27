import climate
import fnmatch
import linnmon
import mimetypes
import os

from .base import Media

logging = climate.get_logger(__name__)


def _subclasses(base):
    '''Recursively yield all known subclasses of the given base class.'''
    for cls in base.__subclasses__():
        yield from _subclasses(cls)
        yield cls


class DB(object):
    def __init__(self, path):
        self.db = linnmon.DB(
            path,
            'path', 'hash4', 'hash8', 'hash16',
            ('tags', lambda rec: {t['name'] for t in rec.get('tags', ())}))

    @property
    def root(self):
        return os.path.dirname(self.db.path)

    @property
    def tag_names(self):
        '''Get a list of all tag names in the database.'''
        return sorted(self.db.keys('tags'))

    def create(self, path, tags=(), path_tags=0):
        '''Build an object for representing the given path.

        Parameters
        ----------
        path : str
            Filesystem path where the media item is stored.
        tags : sequence of str, optional
            Extra user tags to add to this item.
        path_tags : int, optional
            Extract user tags from this many path components, starting from the
            right. For example, if `path` is "/foo/bar/baz/item.jpg" then
            setting this to 0 will add no extra tags, and setting it to 2 would
            add the tags 'bar' and 'baz'.

        Returns
        -------
        item : `illuminatus.base.Media`
            A media item.
        '''
        mime, _ = mimetypes.guess_type(path)
        for cls in _subclasses(Media):
            for pattern in cls.MIME_TYPES:
                if fnmatch.fnmatch(mime, pattern):
                    item = cls(self, dict(path=path, medium=cls.__name__.lower()))
                    for tag in tags:
                        item.add_tag(tag)
                    components = os.path.dirname(path).split(os.sep)
                    while components and path_tags > 0:
                        item.add_tag(components.pop(-1))
                        path_tags -= 1
                    return item
        raise ValueError('no known media types for path {}'.format(path))

    def select_by_path(self, *paths, key='date', reverse=True, offset=0, limit=1 << 31):
        '''Find one or more media pieces by path.

        Parameters
        ----------
        paths : str
            Get items from the database corresponding to these paths.
        key : str, optional
            Record field to use for sorting. Defaults to 'date'.
        reverse : bool, optional
            If True (the default), sort in descending order.
        offset : int, optional
            Return records starting at this offset. Defaults to 0.
        limit : int, optional
            Return only this many records. Defaults to ~2 billion.
        '''
        return self._select(
            self.db.select_with_any, 'path', paths, key, reverse, offset, limit)

    def select_tagged(self, *tags, key='date', reverse=True, offset=0, limit=1 << 31):
        '''Find one or more media pieces by tag.

        This method returns records tagged with all of the specified tags.

        Parameters
        ----------
        tags : sequence of str
            Get items from the database with these tags.
        key : str, optional
            Record field to use for sorting. Defaults to 'date'.
        reverse : bool, optional
            If True (the default), sort in descending order.
        offset : int, optional
            Return records starting at this offset. Defaults to 0.
        limit : int, optional
            Return only this many records. Defaults to ~2 billion.
        '''
        return self._select(
            self.db.select_with_all, 'tags', tags, key, reverse, offset, limit)

    def _select(self, select, name, keys, key, reverse, offset, limit):
        def field(rec):
            '''Get the key field from a record for sorting.'''
            return rec[key]

        def build(rec):
            '''Build an object of the appropriate class given a db record.'''
            for cls in _subclasses(Media):
                if rec.get('medium', '').lower() == cls.__name__.lower():
                    return cls(self, rec)
            raise ValueError('unknown medium for record {}'.format(rec))

        recs = sorted(select(name, *keys), key=field, reverse=reverse)
        return [build(rec) for rec in recs[offset:offset + limit]]

    def exists(self, path):
        '''Check whether a given path exists in the database.'''
        return self.db.has('path', path)

    def insert(self, piece):
        '''Add a new piece to the database.'''
        self.db.insert(**piece.rec)

    def save(self):
        '''Save the current state of the database.'''
        self.db.save()

    def delete(self, path, hide_original_if_path_matches=None):
        '''Remove a piece of media.

        WARNING: If hide_original_if_path_matches contains the path for the
        piece, the original file will be renamed with a hidden (dot) prefix.
        '''
        self.db.delete('path', path)

        # if desired, hide the original file referenced by this photo.
        if hide_original_if_path_matches == path:
            dirname = os.path.dirname(path)
            basename = os.path.basename(path)
            try:
                os.rename(path, os.path.join(
                    dirname, '.illuminatus-removed-' + basename))
            except:
                logging.exception('%s: error renaming source', path)

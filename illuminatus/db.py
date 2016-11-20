import climate
import linnmon
import os

from .photos import Photo
from .sounds import Audio
from .videos import Video

logging = climate.get_logger(__name__)


def _by_date_asc(rec):
    return rec['date']


def _by_date_desc(rec):
    return -rec['date']


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

    def _build(self, rec):
        '''Build an object of the appropriate class given a db record.'''
        for cls in (Photo, Video, Audio):
            if rec.get('medium', '').lower() == cls.__name__.__lower__():
                return cls(self, rec)
        raise ValueError('unknown medium for record {}'.format(rec))

    def select_by_path(self, *paths, sort='newest', offset=0, limit=1 << 31):
        '''Find one or more media pieces by path.'''
        return self._select(
            self.db.select_with_any, 'path', paths, sort, offset, limit)

    def select_tagged(self, *tags, sort='newest', offset=0, limit=1 << 31):
        '''Find media pieces tagged with all the given tags.'''
        return self._select(
            self.db.select_with_all, 'tags', tags, sort, offset, limit)

    def _select(self, select, name, keys, sort, offset, limit):
        if sort.lower() == 'oldest':
            sorter = _by_date_asc
        elif sort.lower() == 'newest':
            sorter = _by_date_desc
        else:
            raise ValueError('unknown sort method {}'.format(sort))
        recs = select(name, *keys, sort=sorter)
        return [self._build(rec) for rec in recs[offset:offset + limit]]

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

import climate
import datetime
import hashlib
import os

from . import db
from . import util

logging = climate.get_logger(__name__)

ORD = {1: 'st', 2: 'nd', 3: 'rd'}


class Media(object):
    class Ops(object):
        Autocontrast = 'autocontrast'
        Contrast = 'contrast'

        Brightness = 'brightness'
        Saturation = 'saturation'
        Hue = 'hue'

        Crop = 'crop'
        Scale = 'scale'
        Rotate = 'rotate'

    def __init__(self, db, record):
        self.db = db
        self.rec = rec

    @property
    def ops(self):
        return self.rec.setdefault('ops', [])

    @property
    def tags(self):
        return set(util.Tag(**t) for t in self.rec.setdefault('tags', []))

    @property
    def stamp(self):
        stamp = self.rec.get('stamp')
        if not stamp:
            return None
        if isinstance(stamp, datetime.datetime):
            return stamp
        return datetime.datetime.strptime(stamp[:19], '%Y-%m-%dT%H:%M:%S')

    @property
    def source_path(self):
        return self.rec['path']

    @property
    def thumb_path(self):
        id = hashlib.md5(self.rec['path']).hexdigest().lower()
        return os.path.join(id[0:2], id[2:4], '{}.{}'.format(id, self.EXTENSION))

    def build_datetime_tags(self):
        if not self.stamp:
            return set()

        def ordinal(n):
            suf = 'th' if n % 100 in (11, 12, 13) else ORD.get(n % 10, 'th')
            return '{}{}'.format(n, suf)

        # for computing the hour tag, we set the hour boundary at 48-past, so
        # that any time from, e.g., 10:48 to 11:47 gets tagged as "11am"
        hour = self.stamp + datetime.timedelta(minutes=12)

        return set(util.Tag(t, 'datetime', s) for s, t in enumerate((
            self.stamp.strftime('%Y'),                # 2009
            self.stamp.strftime('%B'),                # january
            self.stamp.strftime('%A'),                # monday
            ordinal(int(self.stamp.strftime('%d'))),  # 22nd
            hour.strftime('%I%p').strip('0'))))       # 4pm

    def rotate(self, degrees):
        if self.ops and self.ops[-1]['key'] == 'rotate':
            op = self.ops.pop()
            degrees += op['degrees']
        self._add_op('rotate', degrees=degrees % 360)

    def brightness(self, level):
        self._add_op('brightness', level=level)

    def saturation(self, level):
        self._add_op('saturation', level=level)

    def hue(self, level):
        self._add_op('hue', level=level)

    def crop(self, box):
        self._add_op('crop', box=box)

    def scale(self, factor):
        self._add_op('scale', factor=factor)

    def _add_op(self, key, **op):
        op['key'] = key
        self.ops.append(op)
        self.make_thumbnails()
        db.update(self)

    def remove_op(self, index, key):
        if not 0 <= index < len(self.ops):
            return
        if self.ops[index]['key'] != key:
            logging.error('%s: op %d has key %s not %s',
                          self.thumb_path, index, self.ops[index]['key'], key)
            return
        self.ops.pop(index)
        self.make_thumbnails()
        db.update(self)

    def cleanup(self):
        '''Remove thumbnails of this media item.'''
        for size in os.listdir(self.db.root):
            try:
                os.unlink(os.path.join(self.db.root, size, self.thumb_path))
            except:
                pass

    def serialize(self, size):
        '''Serialize this media item as a specific size.'''
        raise NotImplementedError


def create(medium, path, tags, add_path_tags=0):
    '''Create a new Photo from the file at the given path.'''
    m = db.insert(path, medium)

    stamp = util.compute_timestamp_from_exif(m.exif)
    tags = set(tags) | set(util.get_path_tags(path, add_path_tags))

    m.meta = dict(
        stamp=stamp,
        path=m.path,
        userTags=list(sorted(util.normalized_tag_set(tags))),
        exifTags=list(sorted(m.read_exif_tags())))

    m.make_thumbnails()

    db.update(m)

    logging.info('user: %s; exif: %s',
                 ', '.join(m.meta['userTags']),
                 ', '.join(m.meta['exifTags']))

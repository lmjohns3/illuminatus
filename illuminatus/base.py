import climate
import datetime
import os
import re
import subprocess

from . import db
from . import util

logging = climate.get_logger(__name__)

ORD = {1: 'st', 2: 'nd', 3: 'rd'}


class Media:
    class Ops:
        Autocontrast = 'autocontrast'
        Brightness = 'brightness'
        Contrast = 'contrast'
        Crop = 'crop'
        Rotate = 'rotate'
        Saturation = 'saturation'

    def __init__(self, id=-1, path='', meta=None):
        self.id = id
        self.path = path
        self.meta = util.parse(meta or '{}')
        self._exif = None

    @property
    def ops(self):
        return self.meta.setdefault('ops', [])

    @property
    def exif(self):
        if self._exif is None:
            self._exif, = util.parse(subprocess.check_output(
                    ['exiftool', '-charset', 'UTF8', '-json', self.path]
            ).decode('utf-8'))
        return self._exif

    @property
    def tag_set(self):
        return self.datetime_tag_set | self.user_tag_set | self.exif_tag_set

    @property
    def user_tag_set(self):
        return util.normalized_tag_set(self.meta.get('userTags'))

    @property
    def exif_tag_set(self):
        return util.normalized_tag_set(self.meta.get('exifTags'))

    @property
    def datetime_tag_set(self):
        if not self.stamp:
            return set()

        def ordinal(n):
            suf = 'th' if n % 100 in (11, 12, 13) else ORD.get(n % 10, 'th')
            return '{}{}'.format(n, suf)

        # for computing the hour tag, we set the hour boundary at 48-past, so
        # that any time from, e.g., 10:48 to 11:47 gets tagged as "11am"
        hour = self.stamp + datetime.timedelta(minutes=12)

        return util.normalized_tag_set(
            [self.stamp.strftime('%Y'),                # 2009
             self.stamp.strftime('%B'),                # january
             self.stamp.strftime('%A'),                # monday
             ordinal(int(self.stamp.strftime('%d'))),  # 22nd
             hour.strftime('%I%p').strip('0'),         # 4pm
             ])

    @property
    def stamp(self):
        stamp = self.meta.get('stamp')
        if not stamp:
            return None
        if isinstance(stamp, datetime.datetime):
            return stamp
        return datetime.datetime.strptime(stamp[:19], '%Y-%m-%dT%H:%M:%S')

    @property
    def thumb_path(self):
        id = '{:08x}'.format(self.id)
        return os.path.join(id[:-3], '{}.{}'.format(id, self.EXTENSION))

    def to_dict(self):
        return dict(
            id=self.id,
            medium=self.__class__.__name__.lower(),
            path=self.path,
            stamp=self.stamp,
            thumb=self.thumb_path,
            ops=self.ops,
            dateTags=list(self.datetime_tag_set),
            userTags=list(self.user_tag_set),
            exifTags=list(self.exif_tag_set),
        )

    def read_exif_tags(self):
        if not self.exif:
            return set()

        tags = set()

        if 'Model' in self.exif:
            t = self.exif['Model'].lower()
            for s in 'canon nikon kodak digital camera super powershot ed$ is$'.split():
                t = re.sub(s, '', t).strip()
            if t:
                tags.add('kit:{}'.format(t))

        return tags

    def rotate(self, degrees):
        if self.ops and self.ops[-1]['key'] == self.Ops.Rotate:
            op = self.ops.pop()
            degrees += op['degrees']
        self._add_op(self.Ops.Rotate, degrees=degrees % 360)

    def brightness(self, level):
        self._add_op(self.Ops.Brightness, level=level)

    def saturation(self, level):
        self._add_op(self.Ops.Saturation, level=level)

    def crop(self, box):
        self._add_op(self.Ops.Crop, box=box)

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
                          self.path, index, self.ops[index]['key'], key)
            return
        self.ops.pop(index)
        self.make_thumbnails()
        db.update(self)

    def cleanup(self):
        '''Remove thumbnails of this media item.'''
        base = os.path.dirname(db.DB)
        for size in os.listdir(base):
            try:
                os.unlink(os.path.join(base, size, self.thumb_path))
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
        thumb=m.thumb_path,
        userTags=list(sorted(util.normalized_tag_set(tags))),
        exifTags=list(sorted(m.read_exif_tags())))

    m.make_thumbnails()

    db.update(m)

    logging.info('user: %s; exif: %s',
                 ', '.join(m.meta['userTags']),
                 ', '.join(m.meta['exifTags']),
                 )

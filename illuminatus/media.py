import arrow
import climate
import collections
import datetime
import hashlib
import os

from . import tools

logging = climate.get_logger(__name__)

# Ordinal suffix special cases.
_ORD = {1: 'st', 2: 'nd', 3: 'rd'}

# Names of camera models, these will be filtered out of the metadata tags.
_CAMERAS = 'canon nikon kodak digital camera super powershot'.split()

# EXIF tags where we should look for timestamps.
_TIMESTAMP_KEYS = 'DateTimeOriginal CreateDate ModifyDate FileModifyDate'.split()


def _round_to_most_significant_digits(n, digits=1):
    '''Return n rounded to the most significant `digits` digits.'''
    if n < 10 ** digits:
        return n
    shift = 10 ** (len(str(n)) - digits)
    return int(shift * round(n / shift))


Tag = collections.namedtuple('Tag', 'type sort name')
'''A POD class representing a tag of a particular type.'''


class Media(object):
    '''A base class for different types of media.'''

    EXTENSION = None
    MIME_TYPES = ()

    def __init__(self, db, rec):
        '''Initialize this item with a database handle and a data record.

        Parameters
        ----------
        db : :class:`illuminatus.db.DB`
            A handle to the database that stores this item's dictionary.
        rec : dict
            A dictionary containing item information.
        '''
        self.db = db
        self.rec = rec

        self._meta = None
        self._tags = None

        self.rec.setdefault('tags', [])
        self.rec.setdefault('ops', [])

    @property
    def ops(self):
        '''The list of media operations for this item.'''
        return self.rec['ops']

    @property
    def tags(self):
        '''The set of tags currently applied to this item.'''
        if self._tags is None:
            self._tags = set(Tag(**tag) for tag in self.rec['tags'])
        return self._tags

    @property
    def stamp(self):
        '''A timestamp for this item, or None.'''
        stamp = self.rec.get('stamp')
        if not stamp:
            for key in _TIMESTAMP_KEYS:
                stamp = self.meta.get(key)
                if stamp is not None:
                    break
        return arrow.get(stamp).datetime

    @property
    def meta(self):
        '''A dictionary of metadata for this item.'''
        if self._meta is None:
            self._meta = self.rec.get('meta')
            if self._meta is None:
                self._meta = self._load_metadata()
        return self._meta

    @property
    def path(self):
        '''The full source filesystem path for this item.'''
        return self.rec['path']

    @property
    def thumb(self):
        '''The relative filesystem path for this item's thumbnails.'''
        id = hashlib.md5(self.rec['path'].encode('utf-8')).hexdigest().lower()
        return os.path.join(id[0:2], id[2:4], '{}.{}'.format(id, self.EXTENSION))

    def save(self):
        '''Update tags, refresh thumbnails, and save this media item.'''
        self.rec['stamp'] = self.stamp
        self.rec['meta'] = self.meta
        self.rec['tags'] = sorted(
            set(tag for tag in self.tags if tag.type == 'user') |
            self._build_metadata_tags() |
            self._build_datetime_tags())

        output = os.path.join(self.db.root, self.thumb)
        dirname = os.path.dirname(output)
        if not os.path.exists(dirname):
            try:
                os.makedirs(dirname)
            except:
                pass
        self.THUMBNAIL_TOOL(self.path).thumbnail(shape, output)

        self.db.save()

    def delete(self, hide_original_if_path_matches=None):
        '''Remove thumbnails for this media item.

        Parameters
        ----------
        hide_original_if_path_matches : str
            If this is specified and equals the path of this item, the item's
            source file will be renamed to a "deleted" version. Some offline
            process can clean these "deleted" source files as needed.
        '''
        for size in os.listdir(self.db.root):
            dirname = os.path.join(self.db.root, size)
            try:
                os.unlink(os.path.join(dirname, self.thumb))
                if not os.listdir(dirname):
                    os.unlink(dirname)
            except:
                pass

        self.db.delete(self.path, hide_original_if_path_matches)

    def _load_metadata(self):
        '''Load metadata for this item.

        Returns
        -------
        meta : dict
            A dictionary mapping string metadata tags to metadata values.
        '''
        return tools.Exiftool(self.path).parse()

    def _build_metadata_tags(self):
        '''Build a set of metadata tags for this item.

        Returns
        -------
        tags : set
            A set containing `illuminatus.Tag`s derived from the metadata on
            this item.
        '''
        meta = self.meta

        if not meta:
            return set()

        highest = _round_to_most_significant_digits

        tags = set()

        if 'Model' in meta:
            tag = meta['Model'].lower()
            for pattern in _CAMERAS + ['ed$', 'is$']:
                tag = re.sub(pattern, '', tag).strip()
            if tag:
                tags.add('kit:{}'.format(tag))

        if 'FNumber' in meta:
            tag = 'f/{}'.format(round(2 * float(meta['FNumber'])) / 2)
            tags.add(tag.replace('.0', ''))

        iso = meta.get('ISO')
        if iso:
            iso = int(meta['ISO'])
            tags.add('iso:{}'.format(highest(iso, 1 + int(iso > 1000))))

        if 'ShutterSpeed' in meta:
            ss = meta['ShutterSpeed']
            n = -1
            if isinstance(ss, (float, int)):
                n = int(1000 * ss)
            elif ss.startswith('1/'):
                n = int(1000. / float(ss[2:]))
            else:
                raise ValueError('cannot parse ShutterSpeed "{}"'.format(ss))
            tags.add('{}ms'.format(max(1, highest(n))))

        if 'FocalLength' in meta:
            tags.add('{}mm'.format(highest(meta['FocalLength'][:-2])))

        return set(Tag(type='meta', sort=0, name=tag.strip().lower())
                   for tag in tags if tag.strip())

    def _build_datetime_tags(self):
        '''Build a set of datetime tags for this item.

        Returns
        -------
        tags : set
            A set containing `illuminatus.Tag`s derived from the timestamp on
            this item.
        '''
        if not self.stamp:
            return set()

        def ordinal(n):
            suf = 'th' if n % 100 in (11, 12, 13) else _ORD.get(n % 10, 'th')
            return '{}{}'.format(n, suf)

        # for computing the hour tag, we set the hour boundary at 48-past, so
        # that any time from, e.g., 10:48 to 11:47 gets tagged as "11am"
        hour = self.stamp + datetime.timedelta(minutes=12)

        return set(Tag(type='datetime', sort=s, name=t)
                   for s, t in enumerate((
                           self.stamp.strftime('%Y'),                # 2009
                           self.stamp.strftime('%B'),                # january
                           self.stamp.strftime('%A'),                # monday
                           ordinal(int(self.stamp.strftime('%d'))),  # 22nd
                           hour.strftime('%I%p').strip('0'))))       # 4pm

    def add_tag(self, tag):
        '''Add a user tag to this item.

        Parameters
        ----------
        tag : str
            A tag to add.
        '''
        self.tags.add(Tag(sort=0, type='user', name=tag))
        self.rec['tags'] = [tag._asdict() for tag in sorted(self.tags)]
        self.save()

    def remove_tag(self, tag):
        '''Remove a user tag from this item.

        Parameters
        ----------
        tag : str
            A tag to remove.

        Raises
        ------
        KeyError
            If this item does not have the given tag.
        '''
        self.tags.remove(Tag(sort=0, type='user', name=tag))
        self.rec['tags'] = [tag._asdict() for tag in sorted(self.tags)]
        self.save()

    def rotate(self, degrees):
        '''Add an op to rotate this item.

        Parameters
        ----------
        degrees : float
            The number of degrees to rotate the item.
        '''
        if self.ops and self.ops[-1]['key'] == 'rotate':
            op = self.ops.pop()
            degrees += op['degrees']
        self._add_op('rotate', degrees=degrees % 360)

    def brightness(self, percent):
        '''Add an op to change the item's brightness.

        Parameters
        ----------
        percent : float
            The percentage change in the brightness, from 0 to 200.
        '''
        self._add_op('brightness', percent=percent)

    def saturation(self, percent):
        '''Add an op to change the item's saturation.

        Parameters
        ----------
        percent : float
            The percentage change in the saturation, from 0 to 200.
        '''
        self._add_op('saturation', percent=percent)

    def hue(self, percent):
        '''Add an op to change the item's hue.

        Parameters
        ----------
        percent : float
            The percentage rotation in the hue, from 0 (-180 degree rotation) to
            200 (+180 degree rotation).
        '''
        self._add_op('hue', percent=percent)

    def crop(self, box):
        '''Add an op to crop the item.

        Parameters
        ----------
        box : [float, float, float, float]
            A bounding box for the crop, given as [left, top, right, bottom],
            where each side is specified as a percentage of the original. For
            example, a box of [0.1, 0.2, 0.85, 0.75] sets the top-left corner
            at 10% of the width from the left edge and 20% of the height from
            the top, and the bottom-right corner at 15% from the right edge and
            25% from the bottom.
        '''
        self._add_op('crop', box=box)

    def scale(self, factor):
        '''Add an op to scale the item.

        Parameters
        ----------
        factor : float
            A floating-point scale for the item. Values less than 1 shrink the
            item, and values greater than 1 make it larger.
        '''
        self._add_op('scale', factor=factor)

    def contrast(self, percent):
        '''Add an op to change the item's contrast.

        Parameters
        ----------
        percent : float
            The percentage change in the contrast, from 0 to 200.
        '''
        self._add_op('contrast', percent=percent)

    def autocontrast(self, cutoff):
        '''Add an op to set the contrast of the item automatically.

        Parameters
        ----------
        cutoff : float
            The percentile of the histogram to cut when renormalizing.
        '''
        self._add_op('autocontrast', cutoff=cutoff)

    def _add_op(self, key, **op):
        '''Add an op.

        Keyword arguments are added to the op definition.

        The item is saved after adding the op.

        Parameters
        ----------
        key : str
            A string-values op key.
        '''
        op['key'] = key
        self.ops.append(op)
        self.save()

    def remove_op(self, key, index=-1):
        '''Remove an op, provided the key matches (as a "security" measure).

        The item is saved after removing the op.

        Parameters
        ----------
        key : str
            A string-values op key, which must match the op at the given `index`.
        index : int
            An integer index of the op to remove. This can be negative, which
            indexes from the end of the ops list.

        Raises
        ------
        IndexError
            If the given `index` exceeds the number of ops for this item.
        KeyError
            If the op at the specified `index` does not have the given `key`.
        '''
        while index < 0:
            index += len(self.ops)
        if index >= len(self.ops):
            raise IndexError('%s: does not have %d ops', self.thumb, index)
        if self.ops[index]['key'] != key:
            raise KeyError('%s: op %d has key %s not %s',
                           self.thumb, index, self.ops[index]['key'], key)
        self.ops.pop(index)
        self.save()


class Photo(Media):
    EXTENSION = 'jpg'
    MIME_TYPES = ('image/*', )
    THUMBNAIL_TOOL = tools.Convert


class Video(Media):
    EXTENSION = 'mp4'
    MIME_TYPES = ('video/*', )
    THUMBNAIL_TOOL = tools.Ffmpeg

    @property
    def frame_size(self):
        def ints(args):
            return int(args[0]), int(args[1])

        def keys(k):
            return self.meta[k + 'Width'], self.meta[k + 'Height']

        try:
            return ints(keys('Image'))
        except:
            pass
        try:
            return ints(keys('SourceImage'))
        except:
            pass
        try:
            return ints(self.meta['ImageSize'].split('x'))
        except:
            pass

        return -1, -1


class Audio(Media):
    EXTENSION = 'mp3'
    MIME_TYPES = ('audio/*', )
    THUMBNAIL_TOOL = tools.Sox

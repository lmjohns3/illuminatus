import arrow
import base64
import bisect
import click
import collections
import datetime
import hashlib
import os
import re

from . import tools

# Names of camera models, these will be filtered out of the metadata tags.
_CAMERAS = 'canon nikon kodak digital camera super powershot'.split()

# EXIF tags where we should look for timestamps.
_TIMESTAMP_KEYS = 'DateTimeOriginal CreateDate ModifyDate FileModifyDate'.split()


def _round_to_most_significant_digits(n, digits=1):
    '''Return n rounded to the most significant `digits` digits.'''
    nint = n
    if not isinstance(nint, int):
        nint = int(re.search(r'^(\d+).*$', n).group(1))
    if nint < 10 ** digits:
        return nint
    shift = 10 ** (len(str(n)) - digits)
    return int(shift * round(nint / shift))


def _ints(*args):
    '''Convert the arguments to integers.'''
    return tuple(int(a) for a in args)


class Tag(collections.namedtuple('TagBase', 'name source sort weight')):
    '''A POD class representing a tag from a source of data.'''

    DATETIME = 0
    METADATA = 1
    USER = 255

    def __new__(cls, name, source=USER, sort=0, weight=1):
        return super().__new__(cls, str(name).strip().lower(), source, sort, weight)

    def __hash__(self):
        return hash('{}|{}|{}'.format(self.source, self.sort, self.name))

    def __eq__(self, other):
        return self.source == other.source and self.name == other.name

    def __lt__(self, other):
        same_source = self.source == other.source
        return ((self.source < other.source) or
                (same_source and self.sort < other.sort) or
                (same_source and self.sort == other.sort and self.name < other.name))


class Format(object):
    '''A POD class representing an export file format specification.

    Attributes
    ----------
    extension : str
        Filename extension.
    bbox : int
        Maximum size of the output. For photos and videos, exported frames must
        fit within a box of this size, while preserving the original aspect
        ratio.
    fps : str
        Frames per second when exporting audio or video. For videos this can
        be a rational number like "30/1.001" or a basic frame rate like "10".
    channels : int
        Number of channels in exported audio files.
    palette : int
        Number of colors in the palette for exported animated GIFs.
    vcodec : str
        Codec to use for exported video.
    acodec : str
        Name of an audio codec to use when exporting videos. If None, remove
        audio from exported videos.
    abitrate : str
        Bitrate specification for audio in exported videos. If None, remove
        audio from exported videos.
    crf : int
        Quality scale for exporting videos.
    preset : str
        Speed preset for exporting videos.
    '''

    def __init__(self, ext=None, bbox=None, fps=None, channels=1, palette=255,
                 acodec='aac', abitrate='128k', vcodec='libx264', crf=30,
                 preset='medium'):
        self.ext = ext
        self.bbox = bbox
        if isinstance(bbox, int):
            self.bbox = (bbox, bbox)
        self.fps = fps
        self.channels = channels
        self.acodec = acodec
        self.abitrate = abitrate
        self.palette = palette
        self.vcodec = vcodec
        self.crf = crf
        self.preset = preset

    def __str__(self):
        parts = []
        if self.ext is not None:
            parts.append(self.ext)
        if self.bbox is not None:
            parts.append('{}x{}'.format(*self.bbox))
        if self.fps:
            parts.append('fps={}'.format(self.fps))
        for key, default in (('channels', 1),
                             ('palette', 255),
                             ('acodec', 'aac'),
                             ('abitrate', '128k'),
                             ('vcodec', 'libx264'),
                             ('crf', 30),
                             ('preset', 'medium')):
            value = getattr(self, key)
            if value != default:
                parts.append('{}={}'.format(key, value))
        return ','.join(parts)

    @classmethod
    def parse(cls, s):
        '''Parse a string s into a Format.

        The string is expected to consist of one or more parts, separated by
        commas. Each part can be:

          - A bare string matching MMM or MMMxNNN. This is used to specify a
            media geometry, giving the "bbox" property. If MMM is given, it
            designates a geometry of MMMxMMM.
          - A bare string. This is used to specify an output extension, which
            determines the encoding of the output.
          - A string with two halves containing one equals (=). The first half
            gives the name of a :class:`Format` field, while the second
            half gives the value for the field.

        Examples
        --------

        - 100: Use the default file format for the medium (JPG for photos and
               MP4 for movies), and size outputs to fit in a 100x100 box.
        - 100x100: Same as above.
        - bbox=100x100: Same.
        - png,100: Same as above, but use PNG for photo outputs.
        - ext=png,100: Same as above.
        - ext=png,bbox=100: Same as above.

        Parameters
        ----------
        s : str
            A string to parse.
        '''
        kwargs = {}
        for item in s.split(','):
            if '=' in item:
                key, value = item.split('=', 1)
            elif re.match(r'\d+(x\d+)?', item):
                key, value = 'bbox', item
            else:
                key, value = 'ext', item
            if key == 'bbox':
                if 'x' in value:
                    w, h = value.split('x')
                    value = (int(w), int(h))
                else:
                    value = (int(value), int(value))
            if hasattr(value, 'isdigit') and value.isdigit():
                value = int(value)
            kwargs[key] = value
        return cls(**kwargs)


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
        self.rec.setdefault('filters', [])

    @property
    def shape(self):
        m = self.meta
        try:
            return _ints(m['ImageWidth'], m['ImageHeight'])
        except:
            pass
        try:
            return _ints(m['SourceImageWidth'], m['SourceImageHeight'])
        except:
            pass
        try:
            return _ints(*m['ImageSize'].split('x'))
        except:
            pass
        return -1, -1

    @property
    def filters(self):
        '''The list of media filters for this item.'''
        return self.rec['filters']

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
        return arrow.get(stamp)

    @property
    def meta(self):
        '''A dictionary of metadata for this item.'''
        if self._meta is None:
            self._meta = self.rec.get('meta')
            if self._meta is None:
                self._meta = self._load_metadata()
        return self._meta

    @property
    def basename(self):
        '''The base filename for this item.'''
        return os.path.basename(self.path)

    @property
    def path(self):
        '''The full source filesystem path for this item.'''
        return self.rec['path']

    @property
    def path_hash(self):
        '''A string containing the hash of this item's path.'''
        digest = hashlib.md5(self.path.encode('utf-8')).digest()
        return base64.b32encode(digest).strip(b'=').lower().decode('utf-8')

    @property
    def media_id(self):
        '''Database id for this item.'''
        return self.rec['id']

    def save(self):
        '''Save this media item to the database.'''
        self.rec['stamp'] = str(self.stamp)
        self.rec['meta'] = self.meta
        self.rec['tags'] = self.rebuild_tags()
        self.db.update(self.rec)

    def rebuild_tags(self):
        '''Rebuild the tag list for this media item, and clear the cache.

        Returns
        -------
        The rebuilt list of tags.
        '''
        self.rec['tags'] = [
            dict(tag._asdict()) for tag in sorted(
                set(t for t in self.tags if t.source == Tag.USER) |
                self._build_metadata_tags() |
                self._build_datetime_tags())]
        self._tags = None
        return self.rec['tags']

    def export(self, root, fmt=None, force=False, **kwargs):
        '''Export a version of this media item to another location.

        Additional keyword arguments are used to create a :class:`Format` if
        `fmt` is `None`.

        Parameters
        ----------
        root : str
            Save exported media under this root path.
        fmt : :class:`Format`, optional
            Export media with the given :class:`Format`.
        force : bool, optional
            If an exported file already exists, this flag determines what to
            do. If `True` overwrite it; otherwise (the default), return.
        '''
        hash = self.path_hash
        if fmt is None:
            fmt = Format(**kwargs)
        dirname = os.path.join(root, str(fmt), hash[:2])
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        ext = fmt.ext or self.EXTENSION
        output = os.path.join(dirname, '{}.{}'.format(hash, ext))
        if os.path.exists(output) and not force:
            return None
        self._export(fmt, output)
        return output

    def _export(self, fmt, output):
        self.TOOL(self.path, self.shape, self.filters).export(fmt, output)

    def delete(self, hide_original=False):
        '''Remove exported media for this media item.

        WARNING: If `hide_original` is True, the original file will be renamed
        with a hidden (dot) prefix. These hidden prefix files can be garbage
        collected by some external process (e.g., cron).

        Parameters
        ----------
        hide_original : bool
            If this is True, the item's source file will be renamed with an
            ".illuminatus-removed-" prefix.
        '''
        self.db.delete(self.path)

        green_path = click.style(self.path, fg='green')
        click.echo('Removed {} from the database'.format(green_path))

        # if desired, hide the original file referenced by this item.
        if hide_original:
            hidden = os.path.join(
                os.path.dirname(self.path),
                '.illuminatus-removed-' + os.path.basename(self.path))
            os.rename(self.path, hidden)
            click.echo('Renamed {} to {}'.format(
                green_path, click.style(hidden, fg='blue')))

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
            A set containing :class:`Tag`s derived from the metadata on
            this item.
        '''
        if not self.meta:
            return set()

        highest = _round_to_most_significant_digits

        tags = set()

        model = self.meta.get('Model', '').lower()
        for pattern in _CAMERAS + ['ed$', 'is$']:
            model = re.sub(pattern, '', model).strip()
        if model:
            tags.add('kit:{}'.format(model))

        fstop = self.meta.get('FNumber', '')
        if isinstance(fstop, (int, float)) or re.match(r'[.\d]+', fstop):
            tags.add('f/{}'.format(round(2 * float(fstop)) / 2).replace('.0', ''))

        iso = self.meta.get('ISO', '')
        if isinstance(iso, (int, float)) or re.match(r'[.\d]+', iso):
            tags.add('iso:{}'.format(highest(iso, 1 + (int(iso) > 1000))))

        ss = self.meta.get('ShutterSpeed', '')
        ms = None
        if isinstance(ss, (int, float)):
            ms = int(1000 * ss)
        elif re.match(r'1/[.\d]+', ss):
            ms = int(1000 / float(ss[2:]))
        if ms:
            tags.add('{}ms'.format(max(1, highest(ms))))

        mm = self.meta.get('FocalLength', '')
        if isinstance(mm, str):
            match = re.search(r'(\d+)(\.\d+)?\s*mm', mm)
            if match:
                mm = match.group(1)
        if mm:
            tags.add('{}mm'.format(highest(mm)))

        return set(Tag(tag, Tag.METADATA) for tag in tags if tag.strip())

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

        # for computing the hour tag, we set the hour boundary at 49-past, so
        # that any time from, e.g., 10:49 to 11:48 gets tagged as "11am"
        hour = self.stamp + datetime.timedelta(minutes=11)
        k = 4 + hour.hour  # sort by 24-hour value

        return set(Tag(t, Tag.DATETIME, s) for s, t in (
            (0, self.stamp.format('YYYY')),  # 2009
            (1, self.stamp.format('MMMM')),  # january
            (2, self.stamp.format('Do')),    # 22nd
            (3, self.stamp.format('dddd')),  # monday
            (k, hour.format('ha'))))         # 4pm

    def update_stamp(self, when):
        '''Update the timestamp for this item.

        Parameters
        ----------
        when : str
            A modifier for the stamp for this item.
        '''
        try:
            self.rec['stamp'] = arrow.get(when)
        except arrow.parser.ParserError:
            fields = dict(y='years', m='months', d='days', h='hours')
            kwargs = {}
            for spec in re.findall(r'[-+]\d+[ymdh]', when):
                sign, shift, granularity = spec[0], spec[1:-1], spec[-1]
                kwargs[fields[granularity]] = (
                    -1 if sign == '-' else 1) * int(shift)
            self.rec['stamp'] = self.stamp.replace(**kwargs)

    def increment_tag(self, tag):
        '''Add or increment a user tag for this item.

        Parameters
        ----------
        tag : str or :class:`Tag`
            A tag to add. If it is not already present, it will be added with
            weight 1. If it is already present, the weight will increase by 1.
        '''
        if isinstance(tag, str):
            tag = Tag(tag)
        for t in self.tags:
            if t == tag:
                self.tags.remove(tag)
                tag = Tag(name=t.name,
                          source=t.source,
                          sort=t.sort,
                          weight=t.weight + 1)
                break
        self.tags.add(tag)

    def decrement_tag(self, tag):
        '''Decrement the weight of a user tag for this item.

        Parameters
        ----------
        tag : str or :class:`Tag`
            A tag to decrement. The tag's current weight is decreased by 1. If
            the tag's weight is then 0, the tag will be removed. No effect if
            the tag does not exist for this item.
        '''
        if isinstance(tag, str):
            tag = Tag(tag)
        for t in self.tags:
            if t == tag:
                self.tags.remove(tag)
                if t.weight > 1:
                    self.tags.add(Tag(name=t.name,
                                      source=t.source,
                                      sort=t.sort,
                                      weight=t.weight - 1))
                break

    def remove_tag(self, tag):
        '''Remove a user tag from this item.

        Parameters
        ----------
        tag : str or :class:`Tag`
            A tag to remove. No effect if the tag does not exist for this item.
        '''
        if isinstance(tag, str):
            tag = Tag(tag)
        if tag in self.tags:
            self.tags.remove(tag)

    def add_filter(self, filter):
        '''Add a filter to this item.

        The item is *not* saved after adding the filter.

        Parameters
        ----------
        filter : dict
            A dictionary containing filter arguments. The dictionary must have
            a "filter" key that names a valid media filter.
        '''
        self.filters.append(filter)

    def remove_filter(self, filter, index=-1):
        '''Remove a filter if the index matches.

        The item is *not* saved after removing the filter.

        Parameters
        ----------
        filter : str
            A string-valued filter name, which must match the filter at the
            given `index`.
        index : int
            An integer index of the filter to remove. This can be negative,
            which indexes from the end of the filter list.

        Raises
        ------
        IndexError
            If the given `index` exceeds the number of filters for this item.
        KeyError
            If the filter at the specified `index` does not have the given
            `key`.
        '''
        while index < 0:
            index += len(self.filters)
        if index >= len(self.filters):
            raise IndexError('{}: does not have {} filters'.format(
                self.path, index))
        actual_filter = self.filters[index]['filter']
        if actual_filter != filter:
            raise KeyError('{}: filter {} has key {!r}, expected {!r}'.format(
                self.path, index, actual_filter, filter))
        self.filters.pop(index)


class Photo(Media):
    EXTENSION = 'jpg'
    MIME_TYPES = ('image/*', )
    TOOL = tools.Convert


class Video(Media):
    EXTENSION = 'mp4'
    MIME_TYPES = ('video/*', )
    TOOL = tools.Ffmpeg

    def _export(self, fmt, output):
        super()._export(fmt, output)
        poster = os.path.splitext(output)[0] + '.jpg'
        self.TOOL(self.path, self.shape, self.filters).export(fmt, poster)


class Audio(Media):
    EXTENSION = 'mp3'
    MIME_TYPES = ('audio/*', )
    TOOL = tools.Sox

    def _load_metadata(self):
        return {}

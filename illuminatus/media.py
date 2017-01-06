import arrow
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


class Tag(collections.namedtuple('TagBase', 'name source sort')):
    '''A POD class representing a tag from a source of data.'''

    DATETIME = 0
    METADATA = 1
    USER = 255

    def __new__(cls, name, source=USER, sort=0):
        return super().__new__(cls, str(name).strip().lower(), source, sort)

    def __hash__(self):
        return hash('{}|{}|{}'.format(self.source, self.sort, self.name))

    def __eq__(self, other):
        return self.source == other.source and self.name == other.name

    def __lt__(self, other):
        if self.source < other.source:
            return True
        if self.source == other.source:
            if self.sort < other.sort:
                return True
            if self.sort == other.sort:
                return self.name < other.name
        return False


class Media:
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
        return hashlib.md5(self.path.encode('utf-8')).hexdigest().lower()

    @property
    def thumbnail_path(self):
        '''The relative filesystem path for this item's thumbnails.'''
        id = self.path_hash
        name = '{}-{}.{}'.format(
            os.path.splitext(self.basename)[0], id[-8:], self.EXTENSION)
        return os.path.join(id[0:2], id[2:4], name)

    @property
    def media_id(self):
        '''Database id for this item.'''
        return self.rec['id']

    def save(self):
        '''Save this media item to the database.'''
        self.rec.update(self._get_record_updates())
        self.rec['stamp'] = str(self.stamp)
        self.rec['meta'] = self.meta
        self.rec['thumb'] = self.thumbnail_path
        self.rebuild_tags()
        self.db.update(self.rec)

    def thumbnail(self, size, root):
        '''Save a "thumbnailed" version of this media item.

        Parameters
        ----------
        size : int
            Export media with the given size under the `root`.
        root : str
            Save thumbnails under this root path.
        '''
        path = os.path.join(root, str(size), self.thumbnail_path)
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        self._thumbnail(size, path)

    def _thumbnail(self, size, path):
        raise NotImplemented

    def rebuild_tags(self):
        '''Rebuild the tags for this media item using current metadata.'''
        tags = (set(tag for tag in self.tags if tag.source == Tag.USER) |
                self._build_metadata_tags() | self._build_datetime_tags())
        self.rec['tags'] = [dict(tag._asdict()) for tag in sorted(tags)]
        self._tags = None

    def delete(self, hide_original=False):
        '''Remove thumbnails for this media item.

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

        def longest(xs):
            max_length = 0
            max_item = None
            for x in xs:
                if len(x) > max_length:
                    max_length = len(x)
                    max_item = x
            return max_item

        base = os.path.splitext(self.thumbnail_path)[0]
        paths = set(glob.glob(os.path.join(self.db.root, '*', base + '*')))
        while paths:
            path = longest(paths)
            paths.remove(path)
            if path != self.db.root:
                try:
                    os.unlink(path)
                    paths.add(os.path.dirname(path))
                except:
                    pass

        # if desired, hide the original file referenced by this item.
        if hide_original:
            hidden = os.path.join(
                os.path.dirname(self.path),
                '.illuminatus-removed-' + os.path.basename(self.path))
            os.rename(self.path, hidden)
            click.echo('Renamed {} to {}'.format(
                green_path, click.style(hidden, fg='blue')))

    def _get_record_updates(self):
        '''Return updates for our database record.

        Returns
        -------
        A dictionary containing updates we wish to make to our database record.
        '''
        return {}

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

    def add_tag(self, tag):
        '''Add a user tag to this item.

        Parameters
        ----------
        tag : str or :class:`Tag`
            A tag to add.
        '''
        if isinstance(tag, str):
            tag = Tag(tag)
        self.tags.add(tag)

    def remove_tag(self, tag):
        '''Remove a user tag from this item.

        Parameters
        ----------
        tag : str or :class:`Tag`
            A tag to remove.

        Raises
        ------
        KeyError
            If this item does not have the given tag.
        '''
        if isinstance(tag, str):
            tag = Tag(tag)
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

    def _thumbnail(self, size, path):
        tool = tools.Convert(self.path, self.shape, self.filters)
        tool.thumbnail((size, size), path)


class Video(Media):
    EXTENSION = 'mp4'
    MIME_TYPES = ('video/*', )

    def _thumbnail(self, size, path):
        tool = tools.Ffmpeg(self.path, self.shape, self.filters)
        tool.poster((size, size), path.replace('.mp4', '.jpg'))
        tool.export((size, size), path)


class Audio(Media):
    EXTENSION = 'mp3'
    MIME_TYPES = ('audio/*', )

    def _load_metadata(self):
        return {}

    def _thumbnail(self, size, path):
        tool = tools.Sox(self.path, self.shape, self.filters)
        tool.thumbnail((size,), path)

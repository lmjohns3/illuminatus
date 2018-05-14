import arrow
import base64
import click
import collections
import enum
import hashlib
import mimetypes
import numpy as np
import os
import PIL.Image
import re
import sqlalchemy
import sqlalchemy.ext.declarative
import ujson

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Table
from sqlalchemy.orm.attributes import flag_modified

from . import metadata
from . import tools

# a map from bit pattern to hex digit, e.g. (True, False, True, True) --> 'b'
_HEX_DIGITS = {
    tuple(b == '1' for b in '{:04b}'.format(i)): '{:x}'.format(i)
    for i in range(16)
}

# a map from hex digit to hex digits that differ in 1 bit.
_HEX_NEIGHBORS = {
    '{:x}'.format(i): tuple('{:x}'.format(i ^ (1 << j)) for j in range(4))
    for i in range(16)
}


def compute_image_simhash(path, size=8):
    '''Compute a similarity hash for an image.

    Parameters
    ----------
    path : str
        Path to an image file on disk.
    size : int, optional
        Number of pixels per side for the image. The hash will have s * s bits.
        Defaults to 8, giving a 64-bit hash.

    Returns
    -------
    A string containing a hex representation of the similarity hash.
    '''
    gray = PIL.Image.open(path).convert('L')
    px = np.asarray(gray.resize((size + 1, size), PIL.Image.ANTIALIAS))
    bits = (px[:, 1:] > px[:, :-1]).flatten()
    return ''.join(_HEX_DIGITS[tuple(b)] for b in
                   np.split(bits, list(range(4, len(bits), 4))))


def neighboring_simhashes(simhash, within=1):
    '''Generate all neighboring simhashes within a given Hamming distance.

    Parameters
    ----------
    simhash : str
        Sim hash to use for computing neighborhood.
    within : int, optional
        Yield all sim hashes within this Hamming distance.

    Returns
    -------
    The set of sim hashes that are within the given distance from the
    original. Does not include the original.
    '''
    nearby = set()
    if not simhash:
        return nearby
    frontier = {simhash}
    while within:
        within -= 1
        next_frontier = set()
        for sh in frontier:
            if sh not in nearby:
                for i, c in enumerate(sh):
                    for d in _HEX_NEIGHBORS[c]:
                        next_frontier.add(sh[:i] + d + sh[i+1:])
        nearby |= frontier
        frontier = next_frontier
    return (nearby | frontier) - {simhash}


@enum.unique
class Medium(enum.Enum):
    '''Enumeration of different supported media types.'''
    Audio = 1
    Photo = 2
    Video = 3


def medium_for(path):
    '''Determine the appropriate medium for a given path.

    Parameters
    ----------
    path : str
        Filesystem path where the asset is stored.

    Returns
    -------
    A string naming an asset medium. Returns None if no known media types
    handle the given path.
    '''
    mime, _ = mimetypes.guess_type(path)
    for pattern, medium in (('audio/.*', Medium.Audio),
                            ('video/.*', Medium.Video),
                            ('image/.*', Medium.Photo)):
        if re.match(pattern, mime):
            return medium
    return None


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


Model = sqlalchemy.ext.declarative.declarative_base()


class Tag(Model):
    __tablename__ = 'tags'
    __table_args__ = dict(sqlite_autoincrement=True)
    id = Column(Integer, primary_key=True)

    name = Column(String, index=True, nullable=False)

    def __repr__(self):
        return '<Tag {}>'.format(self.name)

    Group = collections.namedtuple('Group', 'index color')

    GROUPS = dict(
        y=Group(0, 'green'),
        m=Group(1, 'green'),
        d=Group(2, 'green'),
        w=Group(3, 'green'),
        h=Group(4, 'green'),
        kit=Group(5, 'cyan'),
        aperture=Group(6, 'cyan'),
        focus=Group(7, 'cyan'),
        geo=Group(8, 'blue'),
    )

    @staticmethod
    def get_or_create(sess, name):
        tag = sess.query(Tag).filter(Tag.name == name).first()
        if not tag:
            tag = Tag(name=name)
            sess.add(tag)
        return tag

    @property
    def sort_key(self):
        group = len(Tag.GROUPS)
        if ':' not in self.name:
            return (1 + len(Tag.GROUPS), self.name)
        group = Tag.GROUPS.get(self.name.split(':')[0])
        if group is None:
            return (len(Tag.GROUPS), self.name)
        return '{:02d}-{}'.format(group.index, self.name)

    @property
    def name_string(self):
        if ':' not in self.name:
            return click.style(self.name, 'blue', bold=True)
        parts = self.name.split(':')
        group = parts.pop(0)
        if group in tuple('ymdwh'):
            name = parts[-1]
            return click.style(name, fg=Tag.GROUPS[group].color, bold=True)
        color = Tag.GROUPS[group].color if group in Tag.GROUPS else 'red'
        return '{}:{}'.format(click.style(group, fg=color),
                              click.style(':'.join(parts), fg=color, bold=True))

    def to_dict(self, weight):
        return dict(id=self.id, name=self.name, sort_key=self.sort_key, weight=weight)


class TextJson(sqlalchemy.types.TypeDecorator):
    impl = sqlalchemy.types.TEXT

    def process_bind_param(self, value, dialect):
        return None if value is None else ujson.dumps(value)

    def process_result_value(self, value, dialect):
        return None if value is None else ujson.loads(value)

JSON = sqlalchemy.types.JSON().with_variant(TextJson, 'sqlite')


asset_tags = Table('asset_tags', Model.metadata,
                   Column('tag_id', Integer, ForeignKey('tags.id')),
                   Column('asset_id', Integer, ForeignKey('assets.id')))


class Asset(Model):
    __tablename__ = 'assets'
    __table_args__ = dict(sqlite_autoincrement=True)
    id = Column(Integer, primary_key=True)

    path = Column(String, unique=True, nullable=False)
    medium = Column(Enum(Medium), index=True, nullable=False)
    stamp = Column(DateTime, index=True, nullable=False)
    lat = Column(Float, index=True)
    lng = Column(Float, index=True)
    simhash = Column(String, index=True)
    fingerprint = Column(String, unique=True)

    meta = Column(JSON, nullable=False, default={})
    filters = Column(JSON, nullable=False, default=[])
    tag_weights = Column(JSON, nullable=False, default={})

    tags = sqlalchemy.orm.relationship(Tag,
                                       backref='assets',
                                       secondary=asset_tags,
                                       lazy='joined')

    TOOLS = {Medium.Audio: tools.Sox,
             Medium.Video: tools.Ffmpeg,
             Medium.Photo: tools.Convert}

    EXTENSIONS = {Medium.Audio: 'mp3',
                  Medium.Video: 'mp4',
                  Medium.Photo: 'jpg'}

    @property
    def shape(self):
        def ints(*args): return tuple(int(a) for a in args)
        m = self.meta
        try:
            return ints(m['ImageWidth'], m['ImageHeight'])
        except:
            pass
        try:
            return ints(m['SourceImageWidth'], m['SourceImageHeight'])
        except:
            pass
        try:
            return ints(*m['ImageSize'].split('x'))
        except:
            pass
        return -1, -1

    @property
    def basename(self):
        '''The base filename for this asset.'''
        return os.path.basename(self.path)

    @property
    def path_hash(self):
        '''A string containing the hash of this asset's path.'''
        digest = hashlib.md5(self.path.encode('utf-8')).digest()
        return base64.b32encode(digest).strip(b'=').lower().decode('utf-8')

    def to_dict(self):
        w = self.tag_weights
        return dict(
            id=self.id,
            path=self.path,
            medium=self.medium,
            stamp=arrow.get(self.stamp).isoformat(),
            lat=self.lat,
            lng=self.lng,
            simhash=self.simhash,
            fingerprint=self.fingerprint,
            metadata=self.meta,
            filters=self.filters,
            tags=[t.to_dict(w.get(t.name, -1.0)) for t in
                  sorted(self.tags, key=lambda t: t.sort_key)],
        )

    def export(self, root, fmt=None, force=False, **kwargs):
        '''Export a version of this media asset to another location.

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
        ext = fmt.ext or Asset.EXTENSIONS[self.medium]
        output = os.path.join(dirname, '{}.{}'.format(hash, ext))
        if os.path.exists(output) and not force:
            return None
        tool = Asset.TOOLS[self.medium]
        tool(self.path, self.shape, self.filters).export(fmt, output)
        if self.medium == Medium.Video:
            poster = os.path.splitext(output)[0] + '.jpg'
            tool(self.path, self.shape, self.filters).export(fmt, poster)
        return output

    def _maybe_hide_original(self, hide_original=False):
        '''Rename the original source for this asset.

        WARNING: If `hide_original` is True, the original file will be renamed
        with a hidden (dot) prefix. These hidden prefix files can be garbage
        collected by some external process (e.g., cron).

        Parameters
        ----------
        hide_original : bool
            If this is True, the item's source file will be renamed with an
            ".illuminatus-removed-" prefix.
        '''
        # if desired, hide the original file referenced by this asset.
        if hide_original:
            hidden = os.path.join(
                os.path.dirname(self.path),
                '.illuminatus-removed-' + os.path.basename(self.path))
            os.rename(target.path, hidden)

    def _init(self):
        '''Initialize a newly created asset.'''
        if not os.path.isfile(self.path):
            return

        with open(self.path, 'rb') as handle:
            self.fingerprint = hashlib.md5(handle.read()).hexdigest()

        if self.medium == Medium.Photo:
            self.simhash = compute_image_simhash(self.path)

        if not self.meta:
            self.meta = tools.Exiftool(self.path).parse()

        stamp = metadata.get_timestamp(self.path, self.meta).datetime
        if stamp is not None or self.stamp is None:
            self.stamp = stamp

        self.lat = metadata.get_latitude(self.meta)
        self.lng = metadata.get_longitude(self.meta)

    def _rebuild_tags(self, sess):
        '''Rebuild the tag list for this asset.

        Parameters
        ----------
        sess : db session
            Database session.
        '''
        user = set(self.tag_weights or {})
        meta = set(metadata.gen_metadata_tags(self.meta))
        stamp = set(metadata.gen_datetime_tags(arrow.get(self.stamp)))
        target = user | meta | stamp
        existing = {tag.name: tag for tag in self.tags}
        for name in target - set(existing):
            self.tags.append(Tag.get_or_create(sess, name))
        for name in set(existing) - target:
            self.tags.remove(existing[name])

    def update_stamp(self, when):
        '''Update the timestamp for this asset.

        Parameters
        ----------
        when : str
            A modifier for the stamp for this asset.
        '''
        try:
            self.stamp = arrow.get(when).datetime
        except arrow.parser.ParserError:
            fields = dict(y='years', m='months', d='days', h='hours')
            kwargs = {}
            for spec in re.findall(r'[-+]\d+[ymdh]', when):
                sign, shift, granularity = spec[0], spec[1:-1], spec[-1]
                kwargs[fields[granularity]] = (-1 if sign == '-' else 1) * int(shift)
            self.stamp = arrow.get(self.stamp).replace(**kwargs).datetime

    def increment_tag(self, tag, weight=1.0):
        '''Add or increment the weight for a tag for this asset.

        Parameters
        ----------
        tag : str or :class:`Tag`
            A tag to add. If the tag does not currently exist for this asset,
            the weight will be set to this value.
        weight : float, optional
            Weight to add to the tag. Defaults to 1.0.
        '''
        if isinstance(tag, Tag):
            tag = tag.name
        if not isinstance(self.tag_weights, dict):
            self.tag_weights = {}
        self.tag_weights[tag] = self.tag_weights.get(tag, 0.0) + weight
        flag_modified(self, 'tag_weights')

    def decrement_tag(self, tag, weight=1.0):
        '''Decrement the weight of a user tag for this asset.

        Parameters
        ----------
        tag : str or :class:`Tag`
            A tag to decrement. If the tag's weight reaches 0, the tag will be
            removed. No effect if the tag does not exist for this asset.
        weight : float, optional
            Decrement the weight by this amount. Defaults to 1.0.
        '''
        if isinstance(tag, Tag):
            tag = tag.name
        if not isinstance(self.tag_weights, dict):
            self.tag_weights = {}
        self.tag_weights[tag] = self.tag_weights.get(tag, 0.0) - weight
        if self.tag_weights[tag] <= 0.0:
            del self.tag_weights[tag]
            flag_modified(self, 'tag_weights')

    def remove_tag(self, tag):
        '''Remove a user tag from this asset.

        Parameters
        ----------
        tag : str or :class:`Tag`
            A tag to remove. No effect if the tag does not exist on this asset.
        '''
        if isinstance(tag, Tag):
            tag = tag.name
        if not isinstance(self.tag_weights, dict):
            self.tag_weights = {}
        if tag in self.tag_weights:
            del self.tag_weights[tag]
            flag_modified(self, 'tag_weights')

    def add_filter(self, filter):
        '''Add a filter to this asset.

        Parameters
        ----------
        filter : dict
            A dictionary containing filter arguments. The dictionary must have
            a "filter" key that names a valid media filter.
        '''
        if not isinstance(self.filters, list):
            self.filters = []
        self.filters.append(filter)
        flag_modified(self, 'filters')

    def remove_filter(self, filter, index=-1):
        '''Remove a filter if the index matches.

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
            If the given `index` exceeds the number of filters for this asset.
        KeyError
            If the filter at the specified `index` does not have the given
            `key`.
        '''
        if not isinstance(self.filters, list):
            self.filters = []
        if not self.filters:
            return
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
        flag_modified(self, 'filters')

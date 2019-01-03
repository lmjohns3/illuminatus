import arrow
import base64
import click
import collections
import contextlib
import hashlib
import numpy as np
import os
import parsimonious.grammar
import PIL.Image
import PIL.ImageCms
import re
import sqlalchemy
import sqlalchemy.ext.declarative
import ujson

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Table
from sqlalchemy.orm.attributes import flag_modified

from . import metadata
from . import tools


Model = sqlalchemy.ext.declarative.declarative_base()


class Tag(Model):
    __tablename__ = 'tags'

    id = Column(Integer, primary_key=True)
    name = Column(String, index=True, nullable=False)

    def __repr__(self):
        return '<Tag {}>'.format(self.name)

    Group = collections.namedtuple('Group', 'match color bold')

    GROUPS = (
        Group(r'(19|20)\d\d', 'yellow', False),
        Group(r'january', 'yellow', False),
        Group(r'february', 'yellow', False),
        Group(r'march', 'yellow', False),
        Group(r'april', 'yellow', False),
        Group(r'may', 'yellow', False),
        Group(r'june', 'yellow', False),
        Group(r'july', 'yellow', False),
        Group(r'august', 'yellow', False),
        Group(r'september', 'yellow', False),
        Group(r'october', 'yellow', False),
        Group(r'november', 'yellow', False),
        Group(r'december', 'yellow', False),
        Group(r'\d(st|nd|rd|th)', 'yellow', False),
        Group(r'\d\d(st|nd|rd|th)', 'yellow', False),
        Group(r'monday', 'yellow', False),
        Group(r'tuesday', 'yellow', False),
        Group(r'wednesday', 'yellow', False),
        Group(r'thursday', 'yellow', False),
        Group(r'friday', 'yellow', False),
        Group(r'saturday', 'yellow', False),
        Group(r'sunday', 'yellow', False),
        Group(r'\dam', 'yellow', False),
        Group(r'\d\dam', 'yellow', False),
        Group(r'\dpm', 'yellow', False),
        Group(r'\d\dpm', 'yellow', False),
        Group(r'kit:\S+', 'green', False),
        Group(r'f:\d[.\d]*', 'green', False),
        Group(r'f:\d\d[.\d]*', 'green', False),
        Group(r'\dmm', 'green', False),
        Group(r'\d\dmm', 'green', False),
        Group(r'\d\d\dmm', 'green', False),
        Group(r'\d\d\d\dmm', 'green', False),
        Group(r'geo:\S+', 'cyan', False),
    )

    @staticmethod
    def get_or_create(sess, name):
        tag = sess.query(Tag).filter(Tag.name == name).first()
        if not tag:
            tag = Tag(name=name)
            sess.add(tag)
        return tag

    @staticmethod
    def with_asset_counts(sess):
        def by_group(tag_dict):
            return tag_dict['group'][0], tag_dict['name']
        q = (sess.query(Tag, sqlalchemy.func.count(AssetTag.c.asset_id))
             .join(AssetTag)
             .group_by(Tag.name))
        return sorted((t.to_dict(c) for t, c in q.all()), key=by_group)

    @property
    def group(self):
        i = 0
        for i, group in enumerate(Tag.GROUPS):
            if re.match(group.match, self.name):
                return i, group
        return i, None

    @property
    def name_string(self):
        _, g = self.group
        if g is not None:
            return click.style(self.name, fg=g.color, bold=g.bold)
        return click.style(self.name, fg='blue', bold=True)

    def to_dict(self, weight=1):
        return dict(
            id=self.id,
            name=self.name,
            group=self.group,
            weight=weight,
        )


class TextJson(sqlalchemy.types.TypeDecorator):
    impl = sqlalchemy.types.TEXT

    def process_bind_param(self, value, dialect):
        return None if value is None else ujson.dumps(value)

    def process_result_value(self, value, dialect):
        return None if value is None else ujson.loads(value)

JSON = sqlalchemy.types.JSON().with_variant(TextJson, 'sqlite')


AssetTag = Table('asset_tags', Model.metadata,
                 Column('tag_id', Integer, ForeignKey('tags.id'), index=True),
                 Column('asset_id', Integer, ForeignKey('assets.id'), index=True))


class Asset(Model):
    __tablename__ = 'assets'

    id = Column(Integer, primary_key=True)
    path = Column(String, unique=True, nullable=False)
    medium = Column(Enum(metadata.Medium), index=True, nullable=False)
    stamp = Column(DateTime, index=True, nullable=False)
    description = Column(String, nullable=False, default='')
    width = Column(Integer, index=True, nullable=False, default=0.0)
    height = Column(Integer, index=True, nullable=False, default=0.0)
    duration = Column(Integer, index=True, nullable=False, default=0.0)
    lat = Column(Float, index=True, nullable=False, default=0.0)
    lng = Column(Float, index=True, nullable=False, default=0.0)
    filters = Column(JSON, nullable=False, default=[])
    meta_tags = Column(JSON, nullable=False, default=[])
    tag_weights = Column(JSON, nullable=False, default={})

    hashes = sqlalchemy.orm.relationship('Hash',
                                         backref='assets',
                                         lazy='joined')

    tags = sqlalchemy.orm.relationship(Tag,
                                       backref='assets',
                                       secondary=AssetTag,
                                       lazy='joined')

    TOOLS = {metadata.Medium.Audio: tools.Sox,
             metadata.Medium.Video: tools.Ffmpeg,
             metadata.Medium.Photo: tools.Convert}

    EXTENSIONS = {metadata.Medium.Audio: 'mp3',
                  metadata.Medium.Video: 'mp4',
                  metadata.Medium.Photo: 'jpg'}

    @property
    def shape(self):
        return self.width, self.height

    @property
    def basename(self):
        '''The base filename for this asset.'''
        return os.path.basename(self.path)

    @property
    def path_hash(self):
        '''A string containing the hash of this asset's path.'''
        digest = hashlib.md5(self.path.encode('utf-8')).digest()
        return base64.b32encode(digest).strip(b'=').lower().decode('utf-8')

    @property
    def md5_hash(self):
        return [h for h in self.hashes if h.flavor == 'md5'][0]

    @property
    def diff8_hashes(self):
        return sorted(h for h in self.hashes if h.flavor == 'diff8')

    @staticmethod
    def matching(sess, query, order=None, limit=None):
        '''Find one or more media assets by parsing a query.

        Parameters
        ----------
        sess : SQLAlchemy
            Database session.
        query : str
            Get assets from the database matching these query clauses.
        order : str
            Order assets by this field.
        limit : int
            Limit the number of returned assets.

        Returns
        -------
          A result set of :class:`Asset`s matching the query.
        '''
        rs = sess.query(Asset)
        if query.strip():
            rs = rs.filter(QueryParser(sess).parse(query))
        if order:
            rs = rs.order_by(parse_order(order))
        if limit:
            rs = rs.limit(limit)
        return rs

    def to_dict(self, exclude_tags=set()):
        w = self.tag_weights
        return dict(
            id=self.id,
            path=self.path,
            path_hash=self.path_hash,
            medium=self.medium.name.lower(),
            filters=self.filters,
            stamp=arrow.get(self.stamp).isoformat(),
            description=self.description,
            shape=(self.width, self.height, self.duration),
            latlng=(self.lat, self.lng),
            hashes=[h.to_dict() for h in self.hashes],
            tags=[t.to_dict(w.get(t.name, -1.0))
                  for t in self.tags
                  if t.name not in exclude_tags],
        )

    def export(self, root, fmt=None, overwrite=False, **kwargs):
        '''Export a version of this media asset to another location.

        Additional keyword arguments are used to create a :class:`Format` if
        `fmt` is `None`.

        Parameters
        ----------
        root : str
            Save exported media under this root path.
        fmt : :class:`Format`, optional
            Export media with the given :class:`Format`.
        overwrite : bool, optional
            If an exported file already exists, this flag determines what to
            do. If `True` overwrite it; otherwise (the default), return.

        Returns
        -------
        The path to the exported file, or None if nothing was exported.
        '''
        hash = self.path_hash
        if fmt is None:
            fmt = Format(**kwargs)
        dirname = os.path.join(root, str(fmt), hash[:2])
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        ext = fmt.ext or Asset.EXTENSIONS[self.medium]
        output = os.path.join(dirname, '{}.{}'.format(hash, ext))
        if os.path.exists(output) and not overwrite:
            return None
        tool = Asset.TOOLS[self.medium]
        tool(self.path, self.shape, self.filters).export(fmt, output)
        if self.medium == metadata.Medium.Video:
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

        meta = tools.Exiftool(self.path).parse()

        stamp = metadata.get_timestamp(self.path, meta).datetime
        if stamp is not None or self.stamp is None:
            self.stamp = stamp

        self.width = metadata.get_width(meta)
        self.height = metadata.get_height(meta)
        self.duration = metadata.get_duration(meta)

        self.lat = metadata.get_latitude(meta)
        self.lng = metadata.get_longitude(meta)

        self.meta_tags = sorted(set(metadata.gen_metadata_tags(meta)))

        self.hashes.append(Hash.compute_md5sum(self.path))
        if self.medium == metadata.Medium.Photo:
            self.hashes.append(Hash.compute_photo_diff(self.path))
            self.hashes.append(Hash.compute_photo_histogram(self.path))
        if self.medium == metadata.Medium.Video:
            for o in range(0, int(self.duration), 30):
                self.hashes.append(Hash.compute_video_diff(self.path, o + 15))

    def _rebuild_tags(self, sess):
        '''Rebuild the tag list for this asset.

        Parameters
        ----------
        sess : db session
            Database session.
        '''
        user = set(self.tag_weights or {})
        meta = set(self.meta_tags or ())
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


# a map from bit pattern to hex digit, e.g. (True, False, True, True) --> 'b'
_HEX_DIGITS = {
    tuple(b == '1' for b in '{:04b}'.format(i)): '{:x}'.format(i)
    for i in range(16)
}

class Hash(Model):
    __tablename__ = 'hashes'

    id = Column(Integer, primary_key=True)
    nibbles = Column(String, index=True, nullable=False)
    flavor = Column(String, index=True, nullable=False)
    offset_sec = Column(Float, nullable=False, default=0.0)
    asset_id = Column(ForeignKey('assets.id'), index=True)

    class Flavor:
        '''Enumeration of different supported hash types.'''
        MD5 = 'md5'
        DIFF_8 = 'diff8'
        HSL_HIST = 'hslhist'

    def __str__(self):
        return ':'.join((click.style(self.flavor, fg='white'),
                         click.style(self.nibbles, fg='white', bold=True)))

    @classmethod
    def compute_md5sum(cls, path):
        '''Compute an MD5 sum based on the contents of a file.

        Parameters
        ----------
        path : str
            Path to a file on disk.

        Returns
        -------
        A Hash instance representing the MD5 sum of this file's contents.
        '''
        with open(path, 'rb') as handle:
            nibbles = hashlib.md5(handle.read()).hexdigest()
        return cls(nibbles=nibbles, flavor=Hash.Flavor.MD5)

    @classmethod
    def compute_photo_diff(cls, path, size=8):
        '''Compute a similarity hash for an image.

        Parameters
        ----------
        path : str
            Path to an image file on disk.
        size : {8}, optional
            Number of pixels, `s`, per side for the image. The hash will have
            `s * s` bits. Only implemented value is 8, giving a 64-bit hash.

        Returns
        -------
        A Hash instance representing the diff hash.
        '''
        if size != 8:
            raise ValueError('Diff hash size must be 8, got {}'.format(size))
        gray = PIL.Image.open(path).convert('L')
        pixels = np.asarray(gray.resize((size + 1, size), PIL.Image.ANTIALIAS))
        bits = (pixels[:, 1:] > pixels[:, :-1]).flatten()
        nibbles = ''.join(_HEX_DIGITS[tuple(b)] for b in
                          np.split(bits, list(range(4, len(bits), 4))))
        return cls(nibbles=nibbles, flavor=Hash.Flavor.DIFF_8)

    @classmethod
    def compute_photo_histogram(cls, path):
        #img = PIL.ImageCms.applyTransform(
        #    PIL.Image.open(path).convert('RGB'),
        #    PIL.ImageCms.buildTransformFromOpenProfiles(
        #        PIL.ImageCms.createProfile('sRGB'),
        #        PIL.ImageCms.createProfile('LAB'),
        #        'RGB', 'LAB'))

        def quantize(counts, bins):
            eps = 1e-6
            parts = np.array([sum(c) for c in np.split(np.array(counts), bins)])
            logp = np.log(eps + parts) - np.log(eps * len(parts) + sum(parts))
            lo, hi = np.percentile(logp, [1, 99])
            quantized = np.linspace(lo, hi, 16).searchsorted(np.clip(logp, lo, hi))
            return ''.join('{:x}'.format(b) for b in quantized)

        #counts = PIL.Image.open(path).convert('L').histogram()
        #return cls(nibbles=quantize(counts, 16), flavor=Hash.Flavor.L_HIST)

        hist = PIL.Image.open(path).convert('HSV').histogram()
        hhist, shist, vhist = np.split(np.asarray(hist), 3)
        return cls(nibbles=''.join((quantize(hhist, 16),
                                    quantize(shist, 8),
                                    quantize(vhist, 8))),
                   flavor=Hash.Flavor.HSL_HIST)

    @classmethod
    def compute_audio_diff(cls, path, size=8):
        raise NotImplementedError

    @classmethod
    def compute_video_diff(cls, path, size=8):
        raise NotImplementedError

    def select_neighbors(self, sess, within=1):
        '''Get all neighboring hashes from the database.

        Parameters
        ----------
        sess : SQLAlchemy
            Database session.
        within : int, optional
            Select all existing hashes within this Hamming distance.

        Returns
        -------
        A query object over neighboring hashes from our hash.
        '''
        return sess.query(Hash).filter(
            Hash.nibbles.in_(_neighboring_hashes(self.nibbles, within)),
            Hash.flavor == self.flavor)

    def to_dict(self):
        return dict(
            nibbles=self.nibbles,
            flavor=self.flavor,
            offset_sec=self.offset_sec,
        )


# a map from hex digit to hex digits that differ in 1 bit.
_HEX_NEIGHBORS = {
    '{:x}'.format(i): tuple('{:x}'.format(i ^ (1 << j)) for j in range(4))
    for i in range(16)
}

def _neighboring_hashes(nibbles, within=1):
    '''Pull all neighboring hashes within a given Hamming distance.

    Parameters
    ----------
    nibbles : str
        Hexadecimal string representing the source hash value.
    within : int, optional
        Identify all hashes within this Hamming distance.

    Returns
    -------
    The set of hashes that are within the given distance from the original.
    Does not include the original.
    '''
    nearby = set()
    if not nibbles:
        return nearby
    frontier = {nibbles}
    while within:
        within -= 1
        next_frontier = set()
        for node in frontier:
            if node not in nearby:
                for i, c in enumerate(node):
                    for d in _HEX_NEIGHBORS[c]:
                        next_frontier.add(node[:i] + d + node[i+1:])
        nearby |= frontier
        frontier = next_frontier
    return (nearby | frontier) - {nibbles}


class QueryParser(parsimonious.NodeVisitor):
    '''Media can be queried using a special query syntax; we parse it here.

    The query syntax permits the following atoms, each of which represents a
    set of media assets in the database:

    - after:S -- selects media with timestamps greater than or equal to S
    - before:S -- selects media with timestamps less than or equal to S
    - path:S -- selects media with S in their paths
    - fp:S -- selects media asset with fingerprint S
    - S -- selects media tagged with S

    The specified sets can be combined using any combination of:

    - x or y -- contains media in either set x or set y
    - x and y -- contains media in both sets x and y
    - not y -- contains media not in set y

    Any of the operators above can be combined multiple times, and parentheses
    can be used to group sets together. For example, a and b or c selects media
    matching both a and b, or c, while a and (b or c) matches both a and d,
    where d consists of things in b or c.
    '''

    grammar = parsimonious.Grammar('''\
    query      = union+
    union      = intersect ( _ 'or' _ intersect )*
    intersect  = negation ( _ 'and' _  negation )*
    negation   = 'not'? _ set
    set        = stamp / path / medium / hash / tag / group
    stamp      = ~'(before|after):[-\d]+'
    path       = ~'path:\S+?'
    medium     = ~'(photo|video|audio)'
    hash       = ~'hash:[a-z0-9]+'
    tag        = ~'[-:\w]+'
    group      = '(' _ query _ ')'
    _          = ~'\s*'
    ''')

    def __init__(self, db):
        self.db = db

    def generic_visit(self, node, children):
        return children or node.text

    def visit_query(self, node, children):
        child, = children
        return child

    def visit_group(self, node, children):
        _, _, child, _, _ = children
        return child

    def visit_union(self, node, children):
        acc, rest = children
        for part in rest:
            acc = sqlalchemy.or_(acc, part[-1])
        return acc

    def visit_intersect(self, node, children):
        acc, rest = children
        for part in rest:
            acc = sqlalchemy.and_(acc, part[-1])
        return acc

    def visit_negation(self, node, children):
        neg, _, [filter] = children
        return sqlalchemy.not_(filter) if neg == ['not'] else filter

    def visit_tag(self, node, children):
        return Asset.tags.any(Tag.name == node.text)

    def visit_stamp(self, node, children):
        comp, value = node.text.split(':', 1)
        value = arrow.get(value, ['YYYY', 'YYYY-MM', 'YYYY-MM-DD']).datetime
        column = Asset.stamp
        return column < value if comp == 'before' else column > value

    def visit_path(self, node, visited_children):
        return Asset.path.ilike('%{}%'.format(node.text.split(':', 1)[1]))

    def visit_hash(self, node, visited_children):
        return Asset.hashes.any(
            Hash.nibbles.ilike('%{}%'.format(node.text.split(':', 1)[1])))

    def visit_medium(self, node, visited_children):
        return Asset.medium == node.text.split(':', 1)[1].capitalize()


def parse_order(order):
    '''Parse an ordering string into a SQL alchemy ordering spec.'''
    if order.lower().startswith('rand'):
        return sqlalchemy.func.random()
    descending = False
    if order.endswith('-'):
        descending = True
        order = order[:-1]
    how = getattr(Asset, order)
    return how.desc() if descending else how


@sqlalchemy.event.listens_for(sqlalchemy.engine.Engine, 'connect')
def set_sqlite_pragma(dbapi_connection, connection_record):
    cur = dbapi_connection.cursor()
    cur.execute('PRAGMA encoding = "UTF-8"')
    cur.execute('PRAGMA foreign_keys = ON')
    cur.execute('PRAGMA journal_mode = WAL')
    cur.execute('PRAGMA synchronous = NORMAL')
    cur.close()


def db_uri(path):
    return 'sqlite:///{}'.format(path)


def engine(path, echo=False):
    return sqlalchemy.create_engine(db_uri(path), echo=echo)


def init(path):
    Model.metadata.create_all(engine(path))


@contextlib.contextmanager
def session(path, echo=False, hide_original_on_delete=False):
    session = sqlalchemy.orm.scoping.scoped_session(
        sqlalchemy.orm.sessionmaker(bind=engine(path, echo)))

    @sqlalchemy.event.listens_for(session, 'before_flush')
    def handle_asset_bookkeeping(sess, ctx, instances):
        for asset in sess.new:
            if isinstance(asset, Asset):
                asset._init()
                asset._rebuild_tags(sess)
        for asset in sess.dirty:
            if isinstance(asset, Asset):
                asset._rebuild_tags(sess)
        for asset in sess.deleted:
            if isinstance(asset, Asset):
                asset._maybe_hide_original(hide_original_on_delete)

    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.remove()

import arrow
import collections
import enum
import itertools
import json
import logging
import os
import re
import sqlalchemy
import sqlalchemy.ext.associationproxy

from . import db
from . import ffmpeg
from . import metadata
from .hashes import Hash
from .tags import Tag


def Format(**kwargs):
    return collections.namedtuple('Format', sorted(kwargs))(**kwargs)


asset_tags = db.Table(
    'asset_tags', db.Model.metadata,
    db.Column('asset_id', db.ForeignKey('assets.id'), nullable=False),
    db.Column('tag_id', db.ForeignKey('tags.id'), nullable=False),
    db.PrimaryKeyConstraint('asset_id', 'tag_id'))


class Asset(db.Model):
    __tablename__ = 'assets'

    @enum.unique
    class Medium(str, enum.Enum):
        '''Enumeration of different supported media types.'''
        Audio = 'audio'
        Photo = 'photo'
        Video = 'video'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String, unique=True, nullable=False)
    medium = db.Column(db.Enum(Medium), index=True, nullable=False)

    path = db.Column(db.String, nullable=False)
    description = db.Column(db.String, nullable=False, default='')

    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    duration = db.Column(db.Float)
    fps = db.Column(db.Float)
    lat = db.Column(db.Float, index=True)
    lng = db.Column(db.Float, index=True)
    stamp = db.Column(db.DateTime, index=True)

    filters = db.Column(db.String, nullable=False, default='[]')

    _tags = sqlalchemy.orm.relationship(
        Tag, secondary=asset_tags, backref='assets', lazy='selectin',
        collection_class=set)
    tags = sqlalchemy.ext.associationproxy.association_proxy(
        '_tags', 'name', creator=lambda name: Tag(name=name))

    def __repr__(self):
        return f'<Asset {self.slug}>'

    @property
    def is_audio(self):
        return self.medium == Asset.Medium.Audio

    @property
    def is_photo(self):
        return self.medium == Asset.Medium.Photo

    @property
    def is_video(self):
        return self.medium == Asset.Medium.Video

    @property
    def click(self):
        return repr(self)

    def similar(self, sess, hash='DIFF_4', min_similarity=0.9):
        similar = set()
        for h in self.hashes:
            if h.flavor.value == hash:
                for neighbor in h.neighbors(sess, min_similarity):
                    similar.add(neighbor.asset)
        return similar - {self}

    def to_dict(self, exclude_tags=()):
        return dict(
            id=self.id,
            path=self.path,
            slug=self.slug,
            medium=self.medium.name.lower(),
            filters=json.loads(self.filters),
            stamp=arrow.get(self.stamp).isoformat(),
            description=self.description,
            width=self.width,
            height=self.height,
            duration=self.duration,
            fps=self.fps,
            lat=self.lat,
            lng=self.lng,
            hashes=[h.to_dict() for h in self.hashes],
            tags=self.tags - set(exclude_tags),
        )

    def update_stamp(self, when):
        '''Update the timestamp for this asset.

        Parameters
        ----------
        when : str
            A modifier for the stamp for this asset.
        '''
        for t in metadata.tags_from_stamp(arrow.get(self.stamp)):
            self.tags.remove(t)

        try:
            self.stamp = arrow.get(when).datetime
        except arrow.parser.ParserError:
            fields = dict(y='years', m='months', d='days', h='hours')
            kwargs = {}
            for spec in re.findall(r'[-+]\d+[ymdh]', when):
                sign, shift, granularity = spec[0], spec[1:-1], spec[-1]
                kwargs[fields[granularity]] = (-1 if sign == '-' else 1) * int(shift)
            self.stamp = arrow.get(self.stamp).shift(**kwargs).datetime

        for t in metadata.tags_from_stamp(arrow.get(self.stamp)):
            self.tags.add(t)

    def add_filter(self, filter):
        '''Add a filter to this asset.

        Parameters
        ----------
        filter : dict
            A dictionary containing filter arguments. The dictionary must have
            a "filter" key that names a valid media filter.
        '''
        filters = json.loads(self.filters)
        filters.append(filter)
        self.filters = json.dumps(filters)

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
        filters = json.loads(self.filters)
        if not filters:
            return
        while index < 0:
            index += len(filters)
        if index >= len(filters):
            raise IndexError(f'{self.slug}: does not have {index} filters')
        actual_filter = filters[index]['filter']
        if actual_filter != filter:
            raise KeyError(f'{self.slug}: filter {index} has key '
                           f'{actual_filter!r}, expected {filter!r}')
        filters.pop(index)
        self.filters = json.dumps(filters)

    def export(self, dirname, basename=None, overwrite=False, **kwargs):
        '''Export a version of an asset to another file.

        Parameters
        ----------
        dirname : str
            Save exported asset in this directory.
        basename : str, optional
            Basename for the exported file; defaults to using the asset's slug.
        overwrite : bool, optional
            If an exported file already exists, this flag determines what to
            do. If `True` overwrite it; otherwise (the default), return.
        **kwargs :
            Additional keyword arguments containing formatting settings: frame
            rate, bounding box, etc.
        '''
        kwargs_ext = kwargs.get('ext')
        basename_ext = os.path.splitext(basename)[1].strip('.') if basename else None
        if kwargs_ext and basename_ext and kwargs_ext != basename_ext:
            logging.warn('Export basename %s != extension %s',
                         basename_ext, kwargs_ext)
        if kwargs_ext is None:
            kwargs_ext = basename_ext
        output = os.path.join(dirname, basename or f'{self.slug}.{kwargs_ext}')
        if overwrite or not os.path.exists(output):
            if not os.path.exists(dirname):
                os.makedirs(dirname)
            ffmpeg.run(self, output, **kwargs)

    def update_from_metadata(self):
        '''Update this asset based on metadata in the file.'''
        meta = metadata.Metadata(self.path)
        self.lat, self.lng = meta.latitude, meta.longitude
        self.width, self.height = meta.width, meta.height
        self.duration = meta.duration
        self.tags.update(meta.tags)
        stamp = meta.stamp or arrow.get(os.path.getmtime(self.path))
        if stamp:
            self.stamp = stamp.datetime
            self.tags.update(metadata.tags_from_stamp(stamp))

    def compute_content_hashes(self):
        '''Compute hashes of asset content.'''
        if self.medium == Asset.Medium.Photo:
            for size in (4, 6, 8):
                self.hashes.add(Hash.compute_photo_diff(self.path, size))
            for size in (4, 8, 16):
                self.hashes.add(Hash.compute_photo_histogram(self.path, 'RGB', size))

        if self.medium == Asset.Medium.Video and self.duration:
            for o in range(0, int(self.duration), 10):
                self.hashes.add(Hash.compute_video_diff(self.path, o + 5))

    def hide_original(self):
        '''Hide the original asset file by renaming it with a . prefix.'''
        dirname, basename = os.path.dirname(self.path), os.path.basename(self.path)
        os.rename(self.path, os.path.join(dirname, f'.illuminatus-removed-{basename}'))


@sqlalchemy.event.listens_for(db.Session, 'before_flush')
def use_existing_tags(sess, context, instances):
    for asset in itertools.chain(sess.new, sess.dirty):
        if isinstance(asset, Asset) and any(t.id is None for t in asset._tags):
            requested = Tag.name.in_(asset.tags)
            existing = dict(sess.query(Tag.name, Tag).filter(requested))
            for tag in list(asset._tags):
                if tag.name in existing:
                    asset.tags.discard(tag.name)
                    asset._tags.add(existing[tag.name])
                    sess.expunge(tag)

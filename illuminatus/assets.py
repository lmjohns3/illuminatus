import arrow
import collections
import enum
import json
import os
import re
import sqlalchemy
import sqlalchemy.ext.associationproxy

from . import db
from . import ffmpeg
from . import metadata
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

    def export(self, dirname, format, basename=None, overwrite=False):
        '''Export a version of an asset to another file.

        Parameters
        ----------
        dirname : str
            Save exported asset in this directory.
        format : tuple
            Export asset with the given format specifier.
        basename : str, optional
            Basename for the exported file; defaults to using the asset's slug.
        overwrite : bool, optional
            If an exported file already exists, this flag determines what to
            do. If `True` overwrite it; otherwise (the default), return.
        '''
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        output = os.path.join(dirname, f'{basename or self.slug}.{format.ext}')
        if overwrite or not os.path.exists(output):
            ffmpeg.run(self, format, output)

    def update_from_metadata(self):
        '''
        '''
        meta = metadata.Metadata(self.path)
        self.lat, self.lng = meta.latitude, meta.longitude
        self.width, self.height = meta.width, meta.height
        self.duration = meta.duration
        for tag in meta.tags:
            self.tags.add(tag)

        stamp = meta.stamp or arrow.get(os.path.getmtime(self.path))
        if stamp:
            self.stamp = stamp.datetime
            for tag in metadata.tags_from_stamp(stamp):
                self.tags.add(tag)

    def compute_content_hashes(self):
        if self.medium == Asset.Medium.Photo:
            self.hashes.extend((
                Hash.compute_photo_diff(self.path, 4),
                Hash.compute_photo_diff(self.path, 8),
                Hash.compute_photo_diff(self.path, 16),
                Hash.compute_photo_histogram(self.path, 'RGB', 16),
            ))

        if self.medium == Asset.Medium.Video and self.duration:
            for o in range(0, int(self.duration), 10):
                self.hashes.append(Hash.compute_video_diff(self.path, o + 5))

    def hide_original(self):
        dirname, basename = os.path.dirname(self.path), os.path.basename(self.path)
        os.rename(self.path, os.path.join(dirname, f'.illuminatus-removed-{basename}'))


@sqlalchemy.event.listens_for(db.Session, 'transient_to_pending')
def _persist(sess, asset):
    if not isinstance(asset, Asset):
        return
    tags = set()
    for tag in asset._tags:
        if tag in sess:
            sess.expunge(tag)
        with sess.no_autoflush:
            tags.add(sess.query(Tag).filter_by(name=tag.name).scalar() or tag)
    asset._tags = tags

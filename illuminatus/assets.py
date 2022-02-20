import arrow
import collections
import itertools
import json
import logging
import os
import PIL.Image
import re
import sqlalchemy
import sqlalchemy.ext.associationproxy
import tempfile

from . import celery
from . import db
from . import ffmpeg
from . import metadata
from .hashes import Hash
from .tags import Tag


_DEFAULT_EXTENSIONS = dict(audio='mp3', photo='jpg', video='mp4')


asset_tags = db.Table(
    'asset_tags', db.Model.metadata,
    db.Column('asset_id', db.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False),
    db.Column('tag_id', db.ForeignKey('tags.id', ondelete='CASCADE'), nullable=False),
    db.PrimaryKeyConstraint('asset_id', 'tag_id'))


class Asset(db.Model):
    __tablename__ = 'assets'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String, unique=True, nullable=False)
    medium = db.Column(db.String, index=True, nullable=False)
    path = db.Column(db.String, nullable=False)

    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    orientation = db.Column(db.Integer)
    duration = db.Column(db.Float)
    video_fps = db.Column(db.Float)
    audio_fps = db.Column(db.Float)
    lat = db.Column(db.Float, index=True)
    lng = db.Column(db.Float, index=True)
    stamp = db.Column(db.DateTime, index=True)

    caption = db.Column(db.String)
    filters = db.Column(db.String)

    _tags = sqlalchemy.orm.relationship(
        Tag, secondary=asset_tags, backref='assets', lazy='selectin',
        collection_class=set)

    tags = sqlalchemy.ext.associationproxy.association_proxy(
        '_tags', 'name', creator=lambda name: Tag(name=name))

    def __repr__(self):
        return self.slug

    @property
    def is_audio(self):
        return self.medium == 'audio'

    @property
    def is_photo(self):
        return self.medium == 'photo'

    @property
    def is_video(self):
        return self.medium == 'video'

    def similar_by_tag(self, sess, min_sim=0.5, limit=20):
        '''
        '''
        if not hasattr(Asset, '_idf'):
            Asset._tags_per_asset = collections.defaultdict(set)
            Asset._assets_per_tag = collections.defaultdict(set)
            for tag, asset in sess.query(asset_tags.c.tag_id, asset_tags.c.asset_id):
                Asset._assets_per_tag[tag].add(asset)
                Asset._tags_per_asset[asset].add(tag)
            Asset._idf = {t: 1 / len(a) for t, a in Asset._assets_per_tag.items()}

        my_tags = Asset._tags_per_asset[self.id]
        candidates = set()
        for tag in my_tags:
            candidates.update(Asset._assets_per_tag[tag])
        scores = {}
        for candidate in candidates - {self.id}:
            cand_tags = Asset._tags_per_asset[candidate]
            sim = (sum(Asset._idf[t] for t in (my_tags & cand_tags)) /
                   sum(Asset._idf[t] for t in (my_tags | cand_tags)))
            if sim >= min_sim:
                scores[candidate] = sim
        return sorted(sess.query(Asset).filter(Asset.id.in_(scores)),
                      key=lambda a: scores[a.id], reverse=True)[:limit]

    def similar_by_content(self, sess, method, max_distance=1):
        '''
        '''
        dupes = set()
        for h in self.hashes:
            if h.method == method:
                dupes.update(n.asset for n in h.neighbors(sess, max_distance))
        return dupes - {self}

    def to_dict(self):
        return dict(
            id=self.id,
            slug=self.slug,
            medium=self.medium,
            path=self.path,
            width=self.width,
            height=self.height,
            orientation=self.orientation,
            duration=self.duration,
            video_fps=self.video_fps,
            audio_fps=self.audio_fps,
            lat=self.lat,
            lng=self.lng,
            stamp=arrow.get(self.stamp).isoformat(),
            caption=self.caption,
            filters=json.loads(self.filters or '[]'),
            hashes=[h.to_dict() for h in self.hashes],
            tags=list(self.tags),
        )

    def update_stamp(self, when):
        '''Update the timestamp for this asset.

        Parameters
        ----------
        when : str
            A modifier for the stamp for this asset.
        '''
        for t in metadata.tags_from_stamp(arrow.get(self.stamp)):
            self.tags.discard(t)

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
            self.maybe_add_tag(t)

    def maybe_add_tag(self, tag):
        '''Potentially add a tag to this asset, after canonicalizing its form.

        Parameters
        ----------
        tag : str
            Tag candidate to add. If this does not contain any word characters,
            it will not be added. Otherwise it will be added after converting
            to canonical form.
        '''
        t = Tag.canonical_form(tag)
        if t:
            self.tags.add(t)

    def maybe_remove_tag(self, tag):
        '''Potentially remove a tag from this asset.

        Parameters
        ----------
        tag : str
            Tag candidate to remove. If this tag does not apply to this asset,
            nothing will be removed.
        '''
        self.tags.discard(Tag.canonical_form(tag))

    def add_path_tags(self, limit):
        '''Add tags to this asset from successive path dirnames.

        Parameters
        ----------
        limit : int
            Maximum number of ancestor directory names to add.
        '''
        for tag in os.path.dirname(self.path).split(os.sep)[::-1][:limit]:
            self.maybe_add_tag(tag)

    def add_filter(self, filter):
        '''Add a filter to this asset.

        Parameters
        ----------
        filter : dict
            A dictionary containing filter arguments. The dictionary must have
            a "filter" key that names a valid media filter.
        '''
        filters = json.loads(self.filters or '[]')
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
        filters = json.loads(self.filters or '[]')
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

    def path_for_export(self, root, name, ext):
        '''Get the default path to use for exporting this asset.

        Parameters
        ----------
        root : str
            Root directory for the export.
        name : str
            Subdirectory name.
        ext : str
            Extension for the exported file.

        Returns
        -------
        The full export file path for default exports.
        '''
        return os.path.join(root, name, self.slug[0], f'{self.slug}.{ext}')

    def export_for_web(self, root, formats, overwrite):
        '''Export asset thumbnails asynchronously to a root dir.

        Parameters
        ----------
        root : str
            A directory for holding thumbnails.
        formats : dict
            Thumbnail format configuration.
        overwrite : bool
            If True, overwrite existing thumbnails.

        Yields
        ------
        Asynchronous results from the export tasks.
        '''
        for name, kwargs in formats[self.medium].items():
            ext = kwargs.get('ext', _DEFAULT_EXTENSIONS[self.medium])
            output = self.path_for_export(root, name, ext)
            kw = dict(slug=self.slug, output=output, overwrite=overwrite, **kwargs)
            # Use celery to call self.export(...) asynchronously.
            yield celery.export.apply_async(kwargs=kw, queue=self.medium)

    def export_for_zip(self, root, formats):
        '''Export assets asynchronously to a root directory for zipping.

        Parameters
        ----------
        root : str
            A directory containing thumbnails to include in the zip.
        formats : str
            The name of a thumbnail format configuration file to load.

        Yields
        ------
        Asynchronous results from the export tasks.
        '''
        stems = [self.stamp.isoformat()[:10], self.slug[:4]]
        stems.extend(tag.name for tag in
                     sorted(self._tags, key=lambda t: t.name)
                     if tag.is_user)
        stem = '-'.join(stems)
        for name, kwargs in formats[self.medium].items():
            ext = kwargs.get('ext', _DEFAULT_EXTENSIONS[self.medium])
            output = os.path.join(root, name, f'{stem}.{ext}')
            kw = dict(slug=self.slug, output=output, **kwargs)
            # Use celery to call self.export(...) asynchronously.
            yield celery.export.apply_async(kwargs=kw, queue=self.medium)

    def export(self, output, overwrite=False, **kwargs):
        '''Export a version of an asset to another file.

        Parameters
        ----------
        output : str
            Save exported asset to this file.
        overwrite : bool, optional
            If an exported file already exists, this flag determines what to
            do. If `True` overwrite it; otherwise (the default), return.
        **kwargs :
            Additional keyword arguments to pass to ffmpeg: frame rate,
            bounding box, etc.
        '''
        if os.path.exists(output) and not overwrite:
            return
        if not os.path.exists(os.path.dirname(output)):
            os.makedirs(os.path.dirname(output))
        ffmpeg.run(self, output, **kwargs)

    def update_from_metadata(self):
        '''Update this asset based on metadata in the file.'''
        meta = metadata.Metadata(self.path)
        self.lat, self.lng = meta.latitude, meta.longitude
        self.width, self.height = meta.width, meta.height
        self.duration = meta.duration
        self.orientation = meta.orientation
        self.video_fps = meta.video_fps
        self.audio_fps = meta.audio_fps
        candidate_tags = set(meta.tags)
        stamp = meta.stamp or arrow.get(os.path.getmtime(self.path))
        if stamp:
            self.stamp = stamp.datetime
            candidate_tags.update(metadata.tags_from_stamp(stamp))
        for tag in candidate_tags:
            self.maybe_add_tag(tag)

    def compute_content_hashes(self):
        '''Compute hashes of asset content.'''
        if self.is_photo:
            rgb = self.open_and_auto_orient()
            #self.hashes.add(Hash.compute_resnet_hash(rgb))
            for size in (4, 8, 16):
                self.hashes.add(Hash.compute_photo_histogram(rgb, 'rgb', size))
            gray = rgb.convert('L')
            for size in (4, 8, 16):
                self.hashes.add(Hash.compute_photo_dhash(gray, size))

        if self.is_audio and self.duration:
            import librosa
            import numpy as np
            sr = 16000
            with tempfile.NamedTemporaryFile(suffix='.wav') as ntf:
                # compute fft with windows separated by 1000 samples
                ffmpeg.convert_to_wav(self.path, sr, ntf.name)
                arr, _ = librosa.core.load(ntf.name, sr=sr)
            spec = np.log(librosa.feature.melspectrogram(
                y=arr, sr=sr, n_fft=2048, hop_length=1000, n_mels=64)).T
            for t in range(0, len(spec), 10 * sr // 1000):
                self.hashes.add(Hash.compute_audio_dhash(spec, t, 8))

        if self.is_video and self.duration:
            for t in range(0, int(self.duration), 10):
                with tempfile.NamedTemporaryFile(suffix='.jpg') as ntf:
                    ffmpeg.extract_frame(self.path, t, ntf.name)
                    img = PIL.Image.open(ntf.name).convert('L')
                self.hashes.add(Hash.compute_video_dhash(img, t, 8))

    def move_to_trash(self, trash):
        '''Move the original asset to a trash folder.'''
        if not os.path.exists(trash):
            os.makedirs(trash)
        basename = os.path.basename(self.path)
        os.rename(self.path, os.path.join(trash, f'{self.slug}-{basename}'))

    def open_and_auto_orient(self):
        '''Open an image and apply transpositions to auto-orient the content.'''
        img = PIL.Image.open(self.path)
        # http://stackoverflow.com/q/4228530
        # https://magnushoff.com/articles/jpeg-orientation/
        for op in {
                2: [PIL.Image.FLIP_LEFT_RIGHT],
                3: [PIL.Image.ROTATE_180],
                4: [PIL.Image.FLIP_TOP_BOTTOM],
                5: [PIL.Image.ROTATE_90, PIL.Image.FLIP_TOP_BOTTOM],
                6: [PIL.Image.ROTATE_270],
                7: [PIL.Image.ROTATE_270, PIL.Image.FLIP_TOP_BOTTOM],
                8: [PIL.Image.ROTATE_90],
        }.get(self.orientation, ()):
            img = img.transpose(op)
        return img


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

import celery
import os

from illuminatus import Asset, Hash, Tag, db, ffmpeg, metadata

app = celery.Celery('illuminatus')
app.config_from_object('celeryconfig')


class Task(celery.Task):
    # http://stackoverflow.com/q/31999269

    _session = None

    def after_return(self, *args, **kwargs):
        if self._session is not None:
            self._session.remove()

    @property
    def session(self):
        if self._session is None:
            _, self._session = db.session(self.conf['db_uri'], verbose=False)
        return self._session


@app.task(base=Task)
def one_asset(id):
    for i, asset in enumerate(one_asset.session.query(Asset)):
        print()
        print(asset.path)
        for h in asset.hashes:
            print(h.flavor, '=', h.nibbles)
            for n in h.select_neighbors(one_asset.session, 2):
                print('-->', n.asset.path)


@app.task(base=Task)
def export(id, dirname, format, basename=None):
    '''Export a version of an asset to another file.

    Parameters
    ----------
    dirname : str
        Save exported asset in this directory.
    format : tuple
        Export asset with the given format specifier.
    overwrite : bool, optional
        If an exported file already exists, this flag determines what to
        do. If `True` overwrite it; otherwise (the default), return.
    '''
    asset = export.session.query(Asset).get(id)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    output = os.path.join(dirname, f'{basename or asset.slug}.{format.ext}')
    if overwrite or not os.path.exists(output):
        ffmpeg.run(asset, format, output)


@app.task(base=Task)
def compute_tags(id):
    asset = compute_tags.session.query(Asset).get(id)

    meta = metadata.Metadata(asset.path)
    asset.lat, asset.lng = meta.latitude, meta.longitude
    asset.width, asset.height = meta.width, meta.height
    asset.duration = meta.duration
    for tag in meta.tags:
        asset.tags.add(tag)

    stamp = meta.stamp or arrow.get(os.path.getmtime(asset.path))
    if stamp:
        asset.stamp = stamp.datetime
        for tag in metadata.tags_from_stamp(stamp):
            asset.tags.add(tag)


@app.task(base=Task)
def compute_hashes(id):
    asset = compute_hashes.session.query(Asset).get(id)
    if asset.medium == Asset.Medium.Photo:
        asset.hashes.extend((
            Hash.compute_photo_diff(asset.path, 4),
            Hash.compute_photo_diff(asset.path, 8),
            Hash.compute_photo_diff(asset.path, 16),
            Hash.compute_photo_histogram(asset.path, 'RGB', 16),
        ))
    if asset.medium == Asset.Medium.Video:
        for o in range(0, int(asset.duration), 10):
            asset.hashes.append(Hash.compute_video_diff(asset.path, o + 5))


@app.task(base=Task)
def hide_original(id):
    '''Rename the original source for this asset.'''
    path = hide_original.session.query(Asset).get(id).path
    dirname, basename = os.path.dirname(path), os.path.basename(path)
    os.rename(path, os.path.join(dirname, f'.illuminatus-removed-{basename}'))

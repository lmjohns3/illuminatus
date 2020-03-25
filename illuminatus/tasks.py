import celery
import os

import illuminatus

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
    '''Export a copy of an asset (usually resized/edited/etc.) to a file.'''
    export.session.query(Asset).get(id).export(dirname, format, basename)


@app.task(base=Task)
def update_from_metadata(id):
    '''Update tags for an asset based on metadata.'''
    sess = update_from_metadata.session
    asset = sess.query(illuminatus.Asset).get(id)
    asset.update_from_metadata()
    sess.add(asset)


@app.task(base=Task)
def compute_content_hashes(id):
    '''Compute content-based hashes for an asset.'''
    sess = compute_content_hashes.session
    asset = sess.query(Asset).get(id)
    asset.compute_content_hashes()
    sess.add(asset)


@app.task(base=Task)
def hide_original(id):
    '''Rename the original source for this asset.'''
    hide_original.session.query(Asset).get(id).hide_original()

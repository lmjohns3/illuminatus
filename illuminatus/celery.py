import celery
import illuminatus
import logging
import os
import random
import sqlalchemy
import time

app = celery.Celery('illuminatus')

app.conf.update(
    accept_content=['json'],
    result_serializer='json',
    task_serializer='json',
    task_create_missing_queues=True,
    broker_url='redis://localhost',
    result_backend='redis://localhost',
    timezone='UTC',
    enable_utc=True,
)


class Task(celery.Task):

    def session(self):
        return illuminatus.db.Session(
            bind=illuminatus.db.engine(app.conf['illuminatus_db']),
            autoflush=False)

    def asset(self, sess, slug):
        return sess.query(illuminatus.Asset).filter_by(slug=slug).scalar()


@app.task(base=Task, bind=True)
def export(self, slug, output, overwrite=False, **kwargs):
    '''Export an asset (usually resized/edited/etc.) to a file on disk.'''
    self.asset(self.session(), slug).export(
        output, overwrite=overwrite, **kwargs)


@app.task(base=Task, bind=True)
def update_from_content(self, slug):
    '''Update tags and hashes for an asset based on file content.'''
    for attempt in range(99):
        sess = self.session()
        asset = self.asset(sess, slug)
        if not asset:
            raise ValueError(slug)
        asset.update_from_metadata()
        asset.compute_content_hashes()
        try:
            sess.commit()
            return
        except sqlalchemy.exc.IntegrityError as _:
            sess.rollback()
            logging.info('%s error -- retry #%s ...', slug, attempt + 1)
            time.sleep(10 * random.random())

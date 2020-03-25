import arrow
import illuminatus
import illuminatus.ffmpeg
import os
import pytest
import tempfile

illuminatus.ffmpeg._DEBUG = 1

TESTDATA = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'testdata')

PHOTO_PATH = os.path.join(TESTDATA, 'photo.jpg')
AUDIO_PATH = os.path.join(TESTDATA, 'audio.mp3')
VIDEO_PATH = os.path.join(TESTDATA, 'video.mp4')

PHOTO_ID = 1
AUDIO_ID = 2
VIDEO_ID = 3

RECORDS = [
    {'path': PHOTO_PATH,
     'medium': illuminatus.Asset.Medium.Photo,
     'stamp': '2015-06-02T09:07',
     'tags': set('ab')},
    {'path': AUDIO_PATH,
     'medium': illuminatus.Asset.Medium.Audio,
     'stamp': '2016-01-02T03:04',
     'tags': set('ac')},
    {'path': VIDEO_PATH,
     'medium': illuminatus.Asset.Medium.Video,
     'stamp': '2010-03-09T05:03',
     'tags': set('bc')},
]

MEDIA = pytest.mark.datafiles(PHOTO_PATH, AUDIO_PATH, VIDEO_PATH)

Asset = illuminatus.Asset
Hash = illuminatus.Hash
Tag = illuminatus.Tag


@pytest.fixture(scope='session')
def engine():
    with tempfile.NamedTemporaryFile(prefix='illuminatus-test-') as path:
        engine = illuminatus.db.engine(path.name, echo=False)
        illuminatus.db.Session.configure(bind=engine)
        yield engine


@pytest.fixture(scope='session')
def tables(engine):
    illuminatus.db.Model.metadata.create_all(engine)
    with engine.connect() as conn:
        illuminatus.db.Session.configure(bind=conn)
        for rec in RECORDS:
            slug = os.path.basename(rec['path']).split('.')[0]
            asset = Asset(medium=rec['medium'],
                          path=rec['path'],
                          slug=slug,
                          stamp=arrow.get(rec['stamp']).datetime,
                          tags=rec['tags'])
            asset.hashes.add(Hash(nibbles=slug, flavor='DIFF_4'))
            sess = illuminatus.db.Session()
            sess.add(asset)
            sess.commit()
    yield
    illuminatus.db.Model.metadata.drop_all(engine)


@pytest.fixture(scope='function')
def sess(engine, tables):
    with engine.connect() as conn:
        illuminatus.db.Session.configure(bind=conn)
        tx = conn.begin_nested()
        sess = illuminatus.db.Session()
        sess.begin_nested()
        yield sess
        sess.close()
        tx.rollback()

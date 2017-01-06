import illuminatus
import illuminatus.media
import illuminatus.tools
import os
import pytest

illuminatus.tools._DEBUG = 2

TESTDATA = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'testdata')

PHOTO_PATH = os.path.join(TESTDATA, 'photo.jpg')
AUDIO_PATH = os.path.join(TESTDATA, 'audio.mp3')
VIDEO_PATH = os.path.join(TESTDATA, 'video.mp4')

PHOTO_ID = 1
AUDIO_ID = 2
VIDEO_ID = 3

RECORDS = [
    {'path': PHOTO_PATH,
     'medium': 'photo',
     'stamp': '2015-06-02T09:07',
     'tags': [
         {'name': 'a', 'source': illuminatus.Tag.USER, 'sort': 0},
         {'name': 'b', 'source': illuminatus.Tag.USER, 'sort': 0},
         {'name': 'c', 'source': illuminatus.Tag.USER, 'sort': 0},
     ]},
    {'path': AUDIO_PATH,
     'medium': 'audio',
     'stamp': '2016-01-02T03:04',
     'tags': [
         {'name': 'b', 'source': illuminatus.Tag.USER, 'sort': 0},
         {'name': 'c', 'source': illuminatus.Tag.USER, 'sort': 0},
     ]},
    {'path': VIDEO_PATH,
     'medium': 'video',
     'stamp': '2010-03-09T05:03',
     'tags': [
         {'name': 'c', 'source': illuminatus.Tag.USER, 'sort': 0},
     ]},
]

MEDIA = pytest.mark.datafiles(*tuple(rec['path'] for rec in RECORDS))


class Item(illuminatus.media.Media):
    EXTENSION = 'deb'  # probably not going to be a common media type?
    MIME_TYPES = ('*debian*package*', )

    def _build_metadata_tags(self):
        return set()

    def _refresh_thumbnails(self):
        pass


@pytest.fixture
def empty_db(tmpdir):
    db = illuminatus.DB(str(tmpdir.mkdir('illuminatus').join('empty.db')))
    db.setup()
    return db


@pytest.fixture
def test_db(tmpdir):
    db = illuminatus.DB(str(tmpdir.mkdir('illuminatus').join('test.db')))
    db.setup()

    for i, rec in enumerate(RECORDS):
        db.create(rec['path'])
        db.update(rec)

    return db

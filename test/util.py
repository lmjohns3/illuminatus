import arrow
import illuminatus
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
     'medium': illuminatus.Medium.Photo,
     'stamp': '2015-06-02T09:07',
     'tag_weights': dict(a=1, b=2, c=3)},
    {'path': AUDIO_PATH,
     'medium': illuminatus.Medium.Audio,
     'stamp': '2016-01-02T03:04',
     'tag_weights': dict(b=2, c=3)},
    {'path': VIDEO_PATH,
     'medium': illuminatus.Medium.Video,
     'stamp': '2010-03-09T05:03',
     'tag_weights': dict(c=3)},
]

MEDIA = pytest.mark.datafiles(*tuple(rec['path'] for rec in RECORDS))


@pytest.fixture
def empty_db(tmpdir):
    path = str(tmpdir.mkdir('illuminatus').join('empty.db'))
    illuminatus.db.init(path)
    return path


@pytest.fixture
def test_db(tmpdir):
    path = str(tmpdir.mkdir('illuminatus').join('test.db'))
    illuminatus.db.init(path)
    with illuminatus.db.session(path) as sess:
        for i, rec in enumerate(RECORDS):
            asset = illuminatus.Asset(path=rec['path'],
                                      medium=rec['medium'],
                                      tag_weights=rec['tag_weights'],
                                      stamp=arrow.get(rec['stamp']).datetime)
            sess.add(asset)
    return path

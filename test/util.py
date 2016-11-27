import climate
import gzip
import illuminatus
import os
import pytest

climate.enable_default_logging()

TESTDATA = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'testdata')

MEDIA = pytest.mark.datafiles(os.path.join(TESTDATA, 'photo.jpg'),
                              os.path.join(TESTDATA, 'audio.wav'),
                              os.path.join(TESTDATA, 'video.mp4'))

TEST_DB = b'''[
{"path": "/a/b/c/photo.jpg",
 "medium": "photo",
 "date": "2015-06-02T09:07",
 "tags": [
  {"name": "a", "type": "user", "sort": 0},
  {"name": "b", "type": "user", "sort": 0},
  {"name": "c", "type": "user", "sort": 0}
 ]},
{"path": "/a/b/c/audio.wav",
 "medium": "audio",
 "date": "2016-01-02T03:04",
 "tags": [
  {"name": "b", "type": "user", "sort": 0},
  {"name": "c", "type": "user", "sort": 0}
 ]},
{"path": "/a/b/c/video.mp4",
 "medium": "video",
 "date": "2010-03-09T05:03",
 "tags": [
  {"name": "c", "type": "user", "sort": 0}
 ]}]'''


class Item(illuminatus.base.Media):
    EXTENSION = 'deb'  # probably not going to be a common media type?
    MIME_TYPES = ('*debian*package*', )

    def _build_metadata_tags(self):
        return set()

    def _refresh_thumbnails(self):
        pass


@pytest.fixture
def empty_db(tmpdir):
    return illuminatus.DB(tmpdir.mkdir('database').join('empty.json.gz'))


@pytest.fixture
def test_db(tmpdir):
    path = tmpdir.mkdir('database').join('test.json.gz')
    path.write_binary(gzip.compress(TEST_DB))
    return illuminatus.DB(str(path))

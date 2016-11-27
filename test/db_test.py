from util import *


def test_create_tags(empty_db):
    img = empty_db.create('/a/b/c/foo.deb', 'x y z'.split(), path_tags=2)
    names = set(t.name for t in img.tags)
    assert 'a' not in names
    assert 'b' in names
    assert 'c' in names
    assert 'x' in names
    assert 'y' in names
    assert 'z' in names


def test_create_unknown(empty_db):
    with pytest.raises(ValueError):
        empty_db.create('abc.xyz')


def test_create(empty_db):
    assert isinstance(empty_db.create('foo.jpg'), illuminatus.Photo)
    assert isinstance(empty_db.create('foo.mp3'), illuminatus.Audio)
    assert isinstance(empty_db.create('foo.mp4'), illuminatus.Video)


def test_exists(test_db):
    assert test_db.exists('/a/b/c/photo.jpg')
    assert not test_db.exists('/a/b/c/foo.deb')


def test_select_by_path(test_db):
    recs = test_db.select_by_path('/a/b/c/photo.jpg',
                                  '/a/b/c/video.mp4',
                                  '/a/b/c/foo.deb')
    assert len(recs) == 2
    assert recs[0].path == '/a/b/c/photo.jpg'
    assert recs[1].path == '/a/b/c/video.mp4'

    recs = test_db.select_by_path('/a/b/c/photo.jpg',
                                  '/a/b/c/video.mp4',
                                  '/a/b/c/foo.deb',
                                  reverse=False)
    assert len(recs) == 2
    assert recs[0].path == '/a/b/c/video.mp4'
    assert recs[1].path == '/a/b/c/photo.jpg'


def test_select_tagged(test_db):
    assert len(test_db.select_tagged('x')) == 0
    assert len(test_db.select_tagged('a')) == 1
    assert len(test_db.select_tagged('b')) == 2
    assert len(test_db.select_tagged('c')) == 3
    assert len(test_db.select_tagged('a', 'b')) == 1
    assert len(test_db.select_tagged('b', 'c')) == 2

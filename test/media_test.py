import arrow

from util import *

A = illuminatus.Asset


def test_add_remove_tags(empty_db):
    with illuminatus.session(empty_db) as sess:
        sess.add(illuminatus.Asset(path='foo', medium=illuminatus.Medium.Photo))
    with illuminatus.session(empty_db) as sess:
        asset = sess.query(A).filter(A.path == 'foo').one()
        assert 'hello' not in set(t.name for t in asset.tags)
    with illuminatus.session(empty_db) as sess:
        asset = sess.query(A).filter(A.path == 'foo').one()
        asset.increment_tag('hello')
        sess.add(asset)
    with illuminatus.session(empty_db) as sess:
        asset = sess.query(A).filter(A.path == 'foo').one()
        assert 'hello' in set(t.name for t in asset.tags)
    with illuminatus.session(empty_db) as sess:
        asset = sess.query(A).filter(A.path == 'foo').one()
        asset.remove_tag('hello')
        sess.add(asset)
    with illuminatus.session(empty_db) as sess:
        asset = sess.query(A).filter(A.path == 'foo').one()
        assert 'hello' not in set(t.name for t in asset.tags)


@pytest.mark.parametrize('when, expected', [
    ('+3y', '2003-03-10T11:12:00+00:00'),
    ('-3y', '1997-03-10T11:12:00+00:00'),
    ('+3m', '2000-06-10T11:12:00+00:00'),
    ('-3m', '1999-12-10T11:12:00+00:00'),
    ('+3d', '2000-03-13T11:12:00+00:00'),
    ('-3d', '2000-03-07T11:12:00+00:00'),
    ('+3h', '2000-03-10T14:12:00+00:00'),
    ('-3h', '2000-03-10T08:12:00+00:00'),
    ('2000-01-01 01:01:01', '2000-01-01T01:01:01+00:00'),
    ('', '2000-03-10T11:12:00+00:00'),
])
def test_update_stamp(empty_db, when, expected):
    with illuminatus.session(empty_db) as sess:
        asset = illuminatus.Asset()
        asset.stamp = arrow.get('2000-03-10T11:12:00+00:00').datetime
        asset.update_stamp(when)
        assert asset.stamp == arrow.get(expected).datetime


@pytest.mark.parametrize('filters', [
    [],
    [dict(filter='rotate', degrees=10)],
    [dict(filter='crop', x1=0.1, y1=0.1, x2=0.8, y2=0.8)],
    [dict(filter='saturation', percent=110)],
    [dict(filter='brightness', percent=90)],
    [dict(filter='autocontrast', percent=10)],
    [dict(filter='hue', degrees=90)],
    [dict(filter='vflip')],
    [dict(filter='hflip')],
])
def test_video_filters(test_db, tmpdir, filters):
    with illuminatus.session(test_db) as sess:
        video = sess.query(A).filter(A.id == VIDEO_ID).one()
        for filter in filters:
            video.add_filter(filter)

        root = tmpdir.mkdir('export')
        size = root.join('100x100')
        thumb = size.join(video.path_hash[:2])
        mp4 = thumb.join(video.path_hash + '.mp4')

        assert root.listdir() == []
        video.export(root=str(root), bbox=100)
        assert sorted(thumb.listdir()) == [str(mp4).replace('.mp4', '.jpg'), mp4]


@pytest.mark.parametrize('filters', [
    [],
    [dict(filter='rotate', degrees=10)],
    [dict(filter='crop', x1=0.1, y1=0.1, x2=0.8, y2=0.8)],
    [dict(filter='saturation', percent=110)],
    [dict(filter='brightness', percent=90)],
    [dict(filter='contrast', percent=90)],
    [dict(filter='autocontrast', percent=1)],
    [dict(filter='hue', degrees=90)],
    [dict(filter='vflip')],
    [dict(filter='hflip')],
])
def test_photo_filters(test_db, tmpdir, filters):
    with illuminatus.session(test_db) as sess:
        photo = sess.query(A).filter(A.id == PHOTO_ID).one()
        for filter in filters:
            photo.add_filter(filter)

        root = tmpdir.mkdir('export')
        size = root.join('100x100')
        thumb = size.join(photo.path_hash[:2])
        jpg = thumb.join(photo.path_hash + '.jpg')

        assert root.listdir() == []
        photo.export(root=str(root), bbox=100)
        assert thumb.listdir() == [jpg]


def test_dhash(test_db):
    with illuminatus.session(test_db) as sess:
        photo = sess.query(A).filter(A.id == PHOTO_ID).one()
        assert photo.compute_dhash(4) == 'a443'
        assert photo.compute_dhash(8) == 'ccc48228397b238e'

import itertools

from util import *


def test_add_remove_tags(empty_db):
    item = Item(empty_db, {})
    assert 'hello' not in set(t.name for t in item.tags)
    item.add_tag('hello')
    assert 'hello' in set(t.name for t in item.tags)
    item.remove_tag('hello')
    assert 'hello' not in set(t.name for t in item.tags)


def test_rebuild_empty(empty_db):
    item = Item(empty_db, {})
    with pytest.raises(KeyError):
        item.rebuild_tags()


def _assert_tags(item, *expected):
    tag_groups = itertools.groupby(sorted(item.tags), key=lambda tag: tag.source)
    for (_, tags), expect in zip(tag_groups, expected):
        assert [t.name for t in tags] == expect.split()


def test_real_metadata_and_datetime_tags(test_db):
    photo, = test_db.select_by_path(PHOTO_PATH)
    photo.rebuild_tags()
    _assert_tags(photo,
                 '2015 june 2nd tuesday 9am',
                 '10ms 20mm f/14 iso:100 kit:dslr-a200',
                 'a b c')


@pytest.mark.parametrize('meta, expected', [
    (dict(), ''),

    (dict(FocalLength='1mm'), '1mm'),
    (dict(FocalLength='11mm'), '10mm'),
    (dict(FocalLength='1 mm'), '1mm'),
    (dict(FocalLength='11    mm'), '10mm'),
    (dict(FocalLength='1.1234 mm'), '1mm'),
    (dict(FocalLength=1.1234), '1mm'),
    (dict(FocalLength='abc'), ''),

    (dict(Model='CANON ULTRA'), 'kit:ultra'),
    (dict(Model='ultra'), 'kit:ultra'),

    (dict(FNumber='1.19'), 'f/1.0'),
    (dict(FNumber='1.77'), 'f/1.5'),
    (dict(FNumber='3.3'), 'f/3.5'),
    (dict(FNumber='abc'), ''),

    (dict(ISO='4'), 'iso:4'),
    (dict(ISO='44'), 'iso:40'),
    (dict(ISO='444'), 'iso:400'),
    (dict(ISO='4444'), 'iso:4400'),
    (dict(ISO='44444'), 'iso:44000'),
    (dict(ISO='abc'), ''),

    (dict(ShutterSpeed='1/12'), '80ms'),
    (dict(ShutterSpeed='1/123'), '8ms'),
    (dict(ShutterSpeed='1/1234'), '1ms'),
    (dict(ShutterSpeed=0.23), '200ms'),
    (dict(ShutterSpeed='abc'), '8ms'),
])
def test_synthetic_metadata_and_datetime_tags(empty_db, meta, expected):
    item = Item(empty_db, {})
    meta['CreateDate'] = '2000-03-10 11:12'
    item._meta = meta
    item.rebuild_tags()
    _assert_tags(item, '2000 march 10th friday 11am', expected, '')


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
    item = Item(empty_db, {})
    item._meta = dict(CreateDate='2000-03-10 11:12')
    assert str(item.stamp) == '2000-03-10T11:12:00+00:00'
    item.update_stamp(when)
    assert str(item.stamp) == expected


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
    video, = test_db.select_by_id(VIDEO_ID)
    for filter in filters:
        video.add_filter(filter)

    root = tmpdir.mkdir('export')
    thumb = root.join(video.path_hash[:2])
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
    photo, = test_db.select_by_id(PHOTO_ID)
    for filter in filters:
        photo.add_filter(filter)

    root = tmpdir.mkdir('export')
    thumb = root.join(photo.path_hash[:2])
    jpg = thumb.join(photo.path_hash + '.jpg')

    assert root.listdir() == []
    photo.export(root=str(root), bbox=100)
    assert thumb.listdir() == [jpg]

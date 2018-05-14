import arrow
import illuminatus.metadata
import itertools

from util import *


def test_real_metadata_and_datetime_tags(test_db):
    A = illuminatus.Asset
    with illuminatus.db.session(test_db) as sess:
        photo = sess.query(A).filter(A.path == PHOTO_PATH).one()
        assert set(t.name for t in photo.tags) == {
            'y:2013', 'm:04:april', 'd:07:7th', 'w:6:sunday', 'h:14:2pm',
            'focus:30mm', 'aperture:f/14', 'kit:dslr-a200', 'a', 'b', 'c'}


@pytest.mark.parametrize('meta, expected', [
    (dict(), ''),

    (dict(FocalLength='1mm'), 'focus:1mm'),
    (dict(FocalLength='11mm'), 'focus:10mm'),
    (dict(FocalLength='1 mm'), 'focus:1mm'),
    (dict(FocalLength='11    mm'), 'focus:10mm'),
    (dict(FocalLength='1.1234 mm'), 'focus:1mm'),
    (dict(FocalLength=1.1234), 'focus:1mm'),
    (dict(FocalLength='abc'), ''),

    (dict(Model='CANON ULTRA'), 'kit:ultra'),
    (dict(Model='ultra'), 'kit:ultra'),

    (dict(FNumber='1.0'), 'aperture:f/1'),
    (dict(FNumber='1.19'), 'aperture:f/1.2'),
    (dict(FNumber='1.77'), 'aperture:f/1.8'),
    (dict(FNumber='3.3'), 'aperture:f/3.3'),
    (dict(FNumber='abc'), ''),
])
def test_synthetic_metadata_tags(meta, expected):
    actual = illuminatus.metadata.gen_metadata_tags(meta)
    assert set(actual) == set(expected.split())


@pytest.mark.parametrize('date, expected', [
    ('2000-03-10 11:12', 'y:2000 m:03:march d:10:10th w:4:friday h:11:11am'),
    ('2000-03-10 11:50', 'y:2000 m:03:march d:10:10th w:4:friday h:12:12pm'),
    ('2000-03-10 13:12', 'y:2000 m:03:march d:10:10th w:4:friday h:13:1pm'),
    ('2000-03-09 13:12', 'y:2000 m:03:march d:09:9th w:3:thursday h:13:1pm'),
])
def test_synthetic_datetime_tags(date, expected):
    actual = illuminatus.metadata.gen_datetime_tags(arrow.get(date))
    assert set(actual) == set(expected.split())


@pytest.mark.parametrize('meta, expected', [
    (dict(), None),
    (dict(GPSPosition='abc'), None),
    (dict(GPSPosition='1 deg 1\' 1" N'), 1.01694),
    (dict(GPSPosition='1 deg 1\' 1" E'), None),
    (dict(GPSLatitude='1 deg 1\' 1" N'), 1.01694),
    (dict(GPSLatitude='5 deg 6\' 7.8" E'), None),
    (dict(GPSPosition='1 deg 2\' 3.4" N, 5 deg 6\' 7.8" E'), 1.03428),
    (dict(GPSPosition='1 deg 2\' 3.4" S, 5 deg 6\' 7.8" E'), -1.03428),
])
def test_synthetic_latitude(meta, expected):
    lat = illuminatus.metadata.get_latitude(meta)
    if lat is None:
        assert lat == expected
    else:
        assert round(lat, 5) == expected


@pytest.mark.parametrize('meta, expected', [
    (dict(), None),
    (dict(GPSPosition='abc'), None),
    (dict(GPSPosition='1 deg 1\' 1" N'), None),
    (dict(GPSLongitude='1 deg 1\' 1" N'), None),
    (dict(GPSLongitude='5 deg 6\' 7.8" E'), 5.10217),
    (dict(GPSPosition='5 deg 6\' 7.8" E'), 5.10217),
    (dict(GPSPosition='1 deg 2\' 3.4" N, 5 deg 6\' 7.8" E'), 5.10217),
    (dict(GPSPosition='1 deg 2\' 3.4" N, 5 deg 6\' 7.8" W'), -5.10217),
])
def test_synthetic_longitude(meta, expected):
    lng = illuminatus.metadata.get_longitude(meta)
    if lng is None:
        assert lng == expected
    else:
        assert round(lng, 5) == expected

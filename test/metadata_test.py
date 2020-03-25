import arrow
import illuminatus.metadata
import json

from util import *


def test_real_metadata_and_datetime_tags(sess):
    A = illuminatus.Asset
    photo = sess.query(A).filter(A.path == PHOTO_PATH).one()
    assert photo.tags == {'a', 'b'}

    meta = illuminatus.metadata.Metadata(photo.path)
    assert set(meta.tags) == {'ƒ-14', 'kit:dslr-a200', '27mm'}
    assert set(illuminatus.metadata.tags_from_stamp(meta.stamp)) == {
        '2013', 'april', '7th', 'sunday', '2pm'}


@pytest.mark.parametrize('meta, expected', [
    (dict(), ''),

    (dict(FocalLength='1mm'), '1mm'),
    (dict(FocalLength='11mm'), '11mm'),
    (dict(FocalLength='1 mm'), '1mm'),
    (dict(FocalLength='11    mm'), '11mm'),
    (dict(FocalLength='1.1234 mm'), '1mm'),
    (dict(FocalLength=1.1234), '1mm'),
    (dict(FocalLength='abc'), ''),

    (dict(Model='CANON ULTRA'), 'kit:ultra'),
    (dict(Model='ultra'), 'kit:ultra'),

    (dict(FNumber='1.0'), 'ƒ-1'),
    (dict(FNumber='1.19'), 'ƒ-1'),
    (dict(FNumber='1.77'), 'ƒ-1'),
    (dict(FNumber='3.3'), 'ƒ-3'),
    (dict(FNumber='abc'), ''),
])
def test_synthetic_metadata_tags(fake_process, meta, expected):
    cmd = ('exiftool', '-json', '-d', '%Y-%m-%d %H:%M:%S', 'foo')
    fake_process.register_subprocess(cmd, stdout=json.dumps([meta]))
    actual = illuminatus.metadata.Metadata(cmd[-1]).tags
    assert set(actual) == set(expected.split())


@pytest.mark.parametrize('date, expected', [
    ('2000-03-10 11:12', '2000 march 10th friday 11am'),
    ('2000-03-10 11:50', '2000 march 10th friday 12pm'),
    ('2000-03-10 13:12', '2000 march 10th friday 1pm'),
    ('2000-03-09 13:12', '2000 march 9th thursday 1pm'),
])
def test_synthetic_datetime_tags(date, expected):
    actual = illuminatus.metadata.tags_from_stamp(arrow.get(date))
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
def test_synthetic_latitude(fake_process, meta, expected):
    cmd = ('exiftool', '-json', '-d', '%Y-%m-%d %H:%M:%S', 'foo')
    fake_process.register_subprocess(cmd, stdout=json.dumps([meta]))
    lat = illuminatus.metadata.Metadata(cmd[-1]).latitude
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
def test_synthetic_longitude(fake_process, meta, expected):
    cmd = ('exiftool', '-json', '-d', '%Y-%m-%d %H:%M:%S', 'foo')
    fake_process.register_subprocess(cmd, stdout=json.dumps([meta]))
    lng = illuminatus.metadata.Metadata(cmd[-1]).longitude
    if lng is None:
        assert lng == expected
    else:
        assert round(lng, 5) == expected

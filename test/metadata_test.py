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

    (dict(FocalLength=1), '1mm'),
    (dict(FocalLength=11), '11mm'),
    (dict(FocalLength=1.1234), '1mm'),

    (dict(Model='CANON ULTRA'), 'kit:ultra'),
    (dict(Model='ultra'), 'kit:ultra'),

    (dict(FNumber=1.0), 'ƒ-1'),
    (dict(FNumber=1.19), 'ƒ-1'),
    (dict(FNumber=1.77), 'ƒ-1'),
    (dict(FNumber=3.3), 'ƒ-3'),
])
def test_synthetic_metadata_tags(fake_process, meta, expected):
    cmd = illuminatus.metadata._EXIFTOOL + ('foo', )
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


@pytest.mark.parametrize('meta, expected_lat, expected_lng', [
    (dict(), None, None),
    (dict(GPSLatitude=1.1, GPSLongitude=2.2), 1.1, 2.2),
    (dict(GPSLatitude=1.1, GPSPosition='4.4 3.3'), 1.1, 3.3),
    (dict(GPSPosition='4.4 3.3', GPSLongitude=2.2), 4.4, 2.2),
    (dict(GPSPosition='4.4 3.3'), 4.4, 3.3),
])
def test_synthetic_latlng(fake_process, meta, expected_lat, expected_lng):
    cmd = illuminatus.metadata._EXIFTOOL + ('foo', )
    fake_process.register_subprocess(cmd, stdout=json.dumps([meta]))
    meta = illuminatus.metadata.Metadata(cmd[-1])
    assert meta.latitude == expected_lat
    assert meta.longitude == expected_lng

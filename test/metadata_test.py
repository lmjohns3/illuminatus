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

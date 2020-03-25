import arrow

from util import *


def test_add_remove_tags(empty_db):
    with illuminatus.session(empty_db) as sess:
        sess.add(illuminatus.Asset(path='foo',
                                   medium=illuminatus.Medium.Photo,
                                   stamp=arrow.get().datetime))
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

import arrow

from util import *


def test_exists(sess):
    assert sess.query(Asset).filter(Asset.path == PHOTO_PATH).count() == 1
    assert sess.query(Asset).filter(Asset.path == 'foo.deb').count() == 0


def test_update(sess):
    photo1 = sess.query(Asset).get(1)
    photo1.tags.add('foo')
    sess.add(photo1)
    photo2 = sess.query(Asset).get(1)
    assert photo1.path == photo2.path
    assert photo1.stamp == photo2.stamp


@pytest.mark.parametrize('when, expected', [
    ('+3y', '2016-04-07T14:01:07'),
    ('-3y', '2010-04-07T14:01:07'),
    ('+3m', '2013-07-07T14:01:07'),
    ('-3m', '2013-01-07T14:01:07'),
    ('+3d', '2013-04-10T14:01:07'),
    ('-3d', '2013-04-04T14:01:07'),
    ('+3h', '2013-04-07T17:01:07'),
    ('-3h', '2013-04-07T11:01:07'),
    ('2000-01-01 01:01:01', '2000-01-01T01:01:01'),
    ('', '2013-04-07T14:01:07'),
])
def test_update_stamp(sess, when, expected):
    asset = sess.query(Asset).get(1)
    asset.update_from_metadata()
    asset.update_stamp(when)
    assert asset.stamp == arrow.get(expected).datetime

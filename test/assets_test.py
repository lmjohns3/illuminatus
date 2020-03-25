import arrow

from util import *

from illuminatus import assets


def test_exists(sess):
    A = assets.Asset
    assert sess.query(A).filter(A.path == PHOTO_PATH).count() == 1
    assert sess.query(A).filter(A.path == 'foo.deb').count() == 0


def test_update(sess):
    A = illuminatus.Asset
    photo1 = sess.query(A).get(1)
    photo1.tags.add('foo')
    sess.add(photo1)
    photo2 = sess.query(A).get(1)
    assert photo1.path == photo2.path
    assert photo1.stamp == photo2.stamp

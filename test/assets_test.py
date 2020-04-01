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


def test_photo_content_hashes(sess):
    asset = sess.query(Asset).get(1)
    asset.compute_content_hashes()
    assert set(h.nibbles for h in asset.hashes) == {
        'photo', '665', '12e1', '387c52', '1fc03b70330e', '8603054c6cb8f30f',
        '3078e01d803300640007007111f13ec11ce116c9a6c9671d6e03354b1a7f80fc'}


def test_audio_content_hashes(sess):
    asset = sess.query(Asset).get(2)
    asset.compute_content_hashes()
    assert set(h.nibbles for h in asset.hashes) == {
        'audio', '30202020a0a0a0b0', '0030303020302024', '2020202020202020',
        '3010202020202020', '0888088898101064', 'b03030202020000c'}


def test_video_content_hashes(sess):
    asset = sess.query(Asset).get(3)
    asset.compute_content_hashes()
    assert set(h.nibbles for h in asset.hashes) == {'video', 'e8e0fcd8b8f8f8f4'}

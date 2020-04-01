import illuminatus

from util import *


@pytest.mark.parametrize('size, expected', [
    (4, '12e1'),
    (6, '98151ce07'),
    (8, '8683054c6cb4f30f'),
])
def test_photo_dhash(sess, size, expected):
    photo = sess.query(Asset).get(PHOTO_ID)
    h = Hash.compute_photo_dhash(
        photo._open_and_auto_orient().convert('L'), size)
    assert h.nibbles == expected


@pytest.mark.parametrize('size, expected', [
    (4, '665'),
    (8, '387c52'),
    (16, '1fc03b70330e'),
])
def test_photo_histogram(sess, size, expected):
    photo = sess.query(Asset).get(PHOTO_ID)
    h = Hash.compute_photo_histogram(
        photo._open_and_auto_orient(), 'rgb', size)
    assert h.nibbles == expected


@pytest.mark.parametrize('nibbles, diff, expected', [
    (None, None, set()),
    ('', None, set()),
    ('0', 0.0, set('0')),
    ('0', 0.49, set('01248')),
    ('0', 0.99, set('0123456789abcde')),
    ('00', 0.1, {'00'}),
    ('00', 0.2, {'00', '01', '02', '04', '08', '10', '20', '40', '80'}),
    ('00', 0.3, {'00', '01', '02', '04', '08', '03', '05', '06', '09', '0a',
                 '0c', '11', '21', '41', '81', '12', '22', '42', '82', '14',
                 '24', '44', '84', '18', '28', '48', '88', '10', '20', '40',
                 '80', '30', '50', '60', '90', 'a0', 'c0', '11', '21', '41',
                 '81', '12', '22', '42', '82', '14', '24', '44', '84', '18',
                 '28', '48', '88'}),
])
def test_neighbors(nibbles, diff, expected):
    assert set(illuminatus.hashes._neighbors(nibbles, diff)) == expected

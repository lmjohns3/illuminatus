from util import *


@pytest.mark.parametrize('size, expected', [
    (4, 'a043'),
    (6, '92211c6c7'),
    (8, 'ccc48228397b238e'),
])
def test_photo_diff(sess, size, expected):
    photo = sess.query(Asset).get(PHOTO_ID)
    diff = Hash.compute_photo_diff(photo.path, size=size)
    assert diff.nibbles == expected


@pytest.mark.parametrize('size, expected', [
    (4, '665'),
    (8, '787c52'),
    (16, '1fc03b703b8e'),
])
def test_photo_histogram(sess, size, expected):
    photo = sess.query(Asset).get(PHOTO_ID)
    hist = Hash.compute_photo_histogram(photo.path, size=size)
    assert hist.nibbles == expected


@pytest.mark.parametrize('nibbles, diff, expected', [
    (None, None, set()),
    ('', None, set()),
    ('0', 0.0, set('0')),
    ('0', 0.5, set('01248')),
    ('0', 1.0, set('0123456789abcde')),
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

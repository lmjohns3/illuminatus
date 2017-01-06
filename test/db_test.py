from util import *


@pytest.mark.parametrize('query, names, ids', [
    ('a', 'a', '123'),
    ('b', 'b', '124'),
    ('c', 'c', '134'),
    ('(c)', 'c', '134'),
    ('((c))', 'c', '134'),

    ('a | a', 'a', '123'),
    ('a & a', 'a', '123'),
    ('a ~ a', 'a', ''),
    ('(a | a)', 'a', '123'),

    ('a | b', 'ab', '1234'),
    ('b | a', 'ab', '1234'),
    ('a & b', 'ab', '12'),
    ('b & a', 'ab', '12'),
    ('a ~ b', 'ab', '3'),
    ('b ~ a', 'ab', '4'),
    ('(b ~ a)', 'ab', '4'),
    ('((b) ~ (a))', 'ab', '4'),

    ('a | b | c', 'abc', '1234'),
    ('(a | b) | c', 'abc', '1234'),
    ('a | (b | c)', 'abc', '1234'),
    ('a & b & c', 'abc', '1'),
    ('(a & b) & c', 'abc', '1'),
    ('a & (b & c)', 'abc', '1'),
    ('a ~ b ~ c', 'abc', ''),
    ('(a ~ b) ~ c', 'abc', ''),
    ('a ~ (b ~ c)', 'abc', '13'),

    ('a ~ (b | c)', 'abc', ''),
    ('(a ~ b) | c', 'abc', '134'),
])
def test_query_parser(query, names, ids):
    id_map = dict(a=set([1, 2, 3]),
                  b=set([1, 2,    4]),
                  c=set([1,    3, 4]))
    parser = illuminatus.db.QueryParser()
    parser.parse(query)
    assert parser.tags == set(names)
    assert len(parser.ops) == 1
    assert parser.compute(id_map) == set(int(x) for x in ids)


def test_create(empty_db):
    assert empty_db.create('abc.xyz') is None

    assert isinstance(empty_db.create('foo.jpg'), illuminatus.Photo)
    assert isinstance(empty_db.create('foo.gif'), illuminatus.Photo)
    assert isinstance(empty_db.create('foo.bmp'), illuminatus.Photo)

    assert isinstance(empty_db.create('foo.mp3'), illuminatus.Audio)
    assert isinstance(empty_db.create('foo.wav'), illuminatus.Audio)

    assert isinstance(empty_db.create('foo.mp4'), illuminatus.Video)
    assert isinstance(empty_db.create('foo.ogv'), illuminatus.Video)


def test_exists(test_db):
    assert test_db.exists(PHOTO_PATH)
    assert not test_db.exists('foo.deb')


def test_update(test_db):
    # load metadata for each item.
    for item in test_db.select_by_id(1, 2, 3):
        item.save()

    assert len(test_db.select('foo')) == 0

    photo1, = test_db.select_by_id(1)
    photo1.add_tag('foo')
    photo1.save()
    assert len(test_db.select('foo')) == 1

    photo2, = test_db.select_by_id(1)
    assert photo1.path == photo2.path
    assert photo1.stamp == photo2.stamp


@pytest.mark.parametrize('ids, kw, expected', [
    ([], {}, []),
    ([1234], {}, []),
    ([PHOTO_ID], {}, ['photo.jpg']),
    ([VIDEO_ID], {}, ['video.mp4']),
    ([PHOTO_ID, VIDEO_ID], {}, ['photo.jpg', 'video.mp4']),
    ([VIDEO_ID, PHOTO_ID], {}, ['photo.jpg', 'video.mp4']),
    ([PHOTO_ID, VIDEO_ID, 1234], {}, ['photo.jpg', 'video.mp4']),
    ([PHOTO_ID, VIDEO_ID], dict(order='stamp'), ['video.mp4', 'photo.jpg']),
    ([PHOTO_ID, VIDEO_ID], dict(order='stamp-'), ['photo.jpg', 'video.mp4']),
])
def test_select_by_id(test_db, ids, kw, expected):
    recs = test_db.select_by_id(*ids, **kw)
    assert len(recs) == len(expected)
    for rec, exp in zip(recs, expected):
        assert rec.path.endswith(exp)


@pytest.mark.parametrize('paths, expected', [
    ([], []),
    (['foo.deb'], []),
    ([PHOTO_PATH], ['photo.jpg']),
    ([PHOTO_PATH, 'foo.deb'], ['photo.jpg']),
    ([VIDEO_PATH], ['video.mp4']),
    ([PHOTO_PATH, VIDEO_PATH], ['photo.jpg', 'video.mp4']),
])
def test_select_by_path(test_db, paths, expected):
    recs = test_db.select_by_path(*paths)
    assert len(recs) == len(expected)
    for rec, exp in zip(recs, expected):
        assert rec.path.endswith(exp)


@pytest.mark.parametrize('query, count', [
    ('x', 0),
    ('a', 1),
    ('b', 2),
    ('c', 3),
    ('a & b', 1),
    ('b | a', 2),

    ('before:2019', 3),
    ('before:2015', 1),
    ('after:2019', 0),
    ('after:2015', 2),
    ('before:2015 & after:2015', 0),

    ('path:photo', 1),
    ('path:video', 1),
])
def test_select(test_db, query, count):
    assert len(test_db.select(query)) == count

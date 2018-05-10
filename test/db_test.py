from util import *


@pytest.mark.parametrize('query, ids', [
    ('a', '123'),
    ('b', '124'),
    ('c', '134'),
    ('(c)', '134'),
    ('((c))', '134'),

    ('a or a', '123'),
    ('a and a', '123'),
    ('not a', '4'),
    ('(a or a)', '123'),

    ('a or b', '1234'),
    ('b or a', '1234'),
    ('a and b', '12'),
    ('b and a', '12'),
    ('a and not b', '3'),
    ('b and not a', '4'),
    ('(b and not a)', '4'),
    ('((b) and not (a))', '4'),

    ('a or b or c', '1234'),
    ('(a or b) or c', '1234'),
    ('a or (b or c)', '1234'),
    ('a and b and c', '1'),
    ('(a and b) and c', '1'),
    ('a and (b and c)', '1'),
    ('a and not b and not c', ''),
    ('(a and not b) and not c', ''),
    ('a and not (b and not c)', '13'),

    ('a and not (b or c)', ''),
    ('(a and not b) or c', '134'),
])
def test_matching_assets_stubs(empty_db, query, ids):
    with illuminatus.session(empty_db) as sess:
        for path, tags in (('1', 'abc'),
                           ('2', 'ab.'),
                           ('3', 'a.c'),
                           ('4', '.bc')):
            sess.add(illuminatus.Asset(
                path=path, medium=illuminatus.Medium.Audio,
                tag_weights={t: 1 for t in tags if t != '.'}))
    with illuminatus.session(empty_db) as sess:
        matching = illuminatus.matching_assets(sess, query)
        assert set(a.path for a in matching) == set(ids)


def test_exists(test_db):
    A = illuminatus.Asset
    with illuminatus.session(test_db) as sess:
        assert sess.query(A).filter(A.path == PHOTO_PATH).count() == 1
        assert sess.query(A).filter(A.path == 'foo.deb').count() == 0


def test_update(test_db):
    A = illuminatus.Asset
    with illuminatus.session(test_db) as sess:
        assert illuminatus.matching_assets(sess, 'foo').count() == 0
        photo1 = sess.query(A).filter(A.id == 1).one()
        photo1.increment_tag('foo')
        sess.add(photo1)
        assert illuminatus.matching_assets(sess, 'foo').count() == 1
        photo2 = sess.query(A).filter(A.id == 1).one()
        assert photo1.path == photo2.path
        assert photo1.stamp == photo2.stamp


@pytest.mark.parametrize('paths, expected', [
    ([], []),
    (['foo.deb'], []),
    ([PHOTO_PATH], ['photo.jpg']),
    ([PHOTO_PATH, 'foo.deb'], ['photo.jpg']),
    ([VIDEO_PATH], ['video.mp4']),
    ([PHOTO_PATH, VIDEO_PATH], ['photo.jpg', 'video.mp4']),
])
def test_select_by_path(test_db, paths, expected):
    A = illuminatus.Asset
    with illuminatus.session(test_db) as sess:
        assert [os.path.basename(a.path) for a in
                sess.query(A).filter(A.path.in_(paths))] == expected


@pytest.mark.parametrize('query, count', [
    ('x', 0),
    ('a', 1),
    ('b', 2),
    ('c', 3),
    ('a and b', 1),
    ('b or a', 2),

    ('before:2019', 3),
    ('before:2015', 1),
    ('after:2019', 0),
    ('after:2015', 2),
    ('before:2015 and after:2015', 0),

    ('path:photo', 1),
    ('path:video', 1),
])
def test_matching_assets(test_db, query, count):
    with illuminatus.session(test_db) as sess:
        assert illuminatus.matching_assets(sess, query).count() == count

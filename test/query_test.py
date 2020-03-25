import arrow

from util import *

from illuminatus import query


@pytest.mark.parametrize('qs, ids', [
    ('x', ''),

    ('a', 'photo audio'),
    ('"a"', 'photo audio'),
    ('b', 'photo video'),
    ('c', 'audio video'),
    ('(c)', 'audio video'),
    ('((c))', 'audio video'),

    ('a or a', 'photo audio'),
    ('a a', 'photo audio'),
    ('not a', 'video'),
    ('(a or a)', 'photo audio'),

    ('a or b', 'photo audio video'),
    ('b or a', 'photo audio video'),
    ('a b', 'photo'),
    ('b a', 'photo'),
    ('a not b', 'audio'),
    ('b not a', 'video'),
    ('(b not a)', 'video'),
    ('((b) not (a))', 'video'),

    ('a or b or c', 'photo audio video'),
    ('(a or b) or c', 'photo audio video'),
    ('a or (b or c)', 'photo audio video'),
    ('a b c', ''),
    ('(a b) c', ''),
    ('a (b c)', ''),
    ('a not b not c', ''),
    ('(a not b) not c', ''),
    ('a not (b not c)', 'audio'),

    ('a not (b or c)', ''),
    ('(a not b) or c', 'audio video'),

    ('hash:aud', 'audio'),

    ('before:2019', 'photo audio video'),
    ('before:2015', 'video'),
    ('after:2019', ''),
    ('after:2015', 'photo audio'),
    ('before:2015 after:2015', ''),

    ('path:photo', 'photo'),
    ('path:video', 'video'),
])
def test_assets(sess, qs, ids):
    matching = query.assets(sess, qs)
    assert set(a.slug for a in matching) == set(ids.split())


def test_parse_order():
    query.parse_order('stamp')

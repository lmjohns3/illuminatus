from util import *


def test_add_remove_tags(empty_db):
    item = Item(empty_db, {})
    assert 'hello' not in set(t.name for t in item.tags)
    item.add_tag('hello')
    assert 'hello' in set(t.name for t in item.tags)
    item.remove_tag('hello')
    assert 'hello' not in set(t.name for t in item.tags)

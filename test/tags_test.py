from util import *


def test_add_remove_tags(sess):
    asset = sess.query(Asset).get(1)
    assert 'hello' not in asset.tags
    asset.tags.add('hello')
    assert 'hello' in asset.tags
    asset.tags.add('hello')
    assert 'hello' in asset.tags
    asset.tags.remove('hello')
    assert 'hello' not in asset.tags
    asset.tags.discard('hello')
    assert 'hello' not in asset.tags

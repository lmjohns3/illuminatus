import illuminatus.importexport

from util import *


def test_import_asset(sess):
    illuminatus.importexport.maybe_import_asset(
        sess, PHOTO_PATH, tags={'uvw'}, path_tags=2)
    asset = sess.query(Asset).get(4)
    assert asset.tags == {'uvw', 'test', 'testdata'}
    assert asset.path == PHOTO_PATH

import illuminatus.importexport
import illuminatus.tasks
import unittest.mock

from util import *


@unittest.mock.patch('illuminatus.tasks.update_from_content')
def test_import_asset(mock, sess):
    illuminatus.importexport.maybe_import_asset(
        sess, PHOTO_PATH, tags={'uvw'}, path_tags=2)
    asset = sess.query(Asset).get(4)
    assert asset.path == PHOTO_PATH
    mock.delay.assert_called()

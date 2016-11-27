from util import *


def test_command():
    cmd = illuminatus.tools.Command(['echo', '-n', 'hello'])
    assert cmd.run().stdout == b'hello'

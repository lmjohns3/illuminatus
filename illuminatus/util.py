import datetime
import os


def ensure_path(*args):
    '''Ensure the directory for the given path exists.'''
    path = os.path.join(*args)
    dirname = os.path.dirname(path)
    if not os.path.exists(dirname):
        try:
            os.makedirs(dirname)
        except:
            pass
    return path


def round_to_highest_digits(n, digits=1):
    '''Return n rounded to the top `digits` digits.'''
    if n < 10 ** digits:
        return n
    shift = 10 ** (len(str(n)) - digits)
    return int(shift * round(n / shift))


def get_dirnames(path, count):
    '''Return the most specific `count` directory components from `path`.'''
    for i, t in enumerate(reversed(os.path.dirname(path).split(os.sep))):
        if i == count:
            break
        if t.strip():
            yield t.strip()


def compute_timestamp_from_exif(exif):
    '''Parse a timestamp from EXIF metadata.'''
    for key in ('DateTimeOriginal', 'CreateDate', 'ModifyDate', 'FileModifyDate'):
        raw = exif.get(key)
        if not raw:
            continue
        for fmt in ('%Y:%m:%d %H:%M:%S', '%Y:%m:%d %H:%M+%S'):
            try:
                return datetime.datetime.strptime(raw[:19], fmt)
            except:
                pass
    return datetime.datetime.now()


class Tag(object):
    '''A POD class representing a tag of a particular type.'''

    def __init__(self, name, type='user', sort=0):
        self.name = name
        self.type = type
        self.sort = sort  # the key to use when sorting this tag.

    def __hash__(self):
        return hash(self.name + self.type)

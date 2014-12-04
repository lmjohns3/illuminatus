import datetime
import json
import os
import re


def parse(x):
    return json.loads(x)


def stringify(x):
    h = lambda z: z.isoformat() if isinstance(z, datetime.datetime) else None
    return json.dumps(x, default=h)


def ensure_path(*args):
    p = os.path.join(*args)
    dirname = os.path.dirname(p)
    if not os.path.exists(dirname):
        try:
            os.makedirs(dirname)
        except:
            pass
    return p


def round_to_highest_digits(n, digits=1):
    '''Return n rounded to the top `digits` digits.'''
    n = float(n)
    if n < 10 ** digits:
        return int(n)
    shift = 10 ** (len(str(int(n))) - digits)
    return int(shift * round(n / shift))


def get_path_tags(path, add_path_tags):
    for i, t in enumerate(reversed(os.path.dirname(path).split(os.sep))):
        if i == add_path_tags:
            break
        if t.strip():
            yield t.strip()


def compute_timestamp_from_exif(exif):
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


def normalized_tag_set(seq, sep=None):
    '''Return a normalized set of tags from the given sequence.'''
    if not seq:
        return set()
    if isinstance(seq, str):
        seq = seq.split(sep)
    return set(t.lower().strip() for t in seq if t.strip())


MONTHS = ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']
DAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
EXIF_TAG_RE = re.compile(r'^(f/[\d\.]+|\d+mm|\d+ms|iso:\d+|kit:.*|photo|video)$')
DATE_TAG_RE = re.compile('^([12]\d{3}|\d+(st|nd|rd|th)|\d+[ap]m|[adefhimnorstuw]+day|(jan|febr)uary|march|april|may|june|july|august|(sept|nov|dec)ember|october)$')

def tag_class(tag):
    if DATE_TAG_RE.match(tag):
        return 'date'
    if EXIF_TAG_RE.match(tag):
        return 'exif'
    return 'user'

def tag_sort_key(tag):
    subgroup = ordinal = 0
    group = 2
    if EXIF_TAG_RE.match(tag):
        group = 1
    if DATE_TAG_RE.match(tag):
        group = 0
        if re.match(r'^\d+[ap]m$', tag):
            subgroup = 1 if tag.endswith('am') else 2
            ordinal = 0 if tag.startswith('12') else 1
            if re.match(r'^\d[ap]m$', tag):
                tag = '0' + tag
        elif re.match(r'^[adefhimnorstuw]+day$', tag):
            subgroup = 3
            ordinal = DAYS.index(tag)
        elif re.match(r'^\d+(st|nd|rd|th)$', tag):
            subgroup = 4
            if re.match('^\d\D', tag):
                tag = '0' + tag
        elif re.match(r'^[12]\d{3}$', tag):
            subgroup = 6
        else:
            subgroup = 5
            ordinal = '{:02d}'.format(MONTHS.index(tag))
    return '{}:{}:{}:{}'.format(group, subgroup, ordinal, tag)

def sort_tags(tags):
    return sorted(tags, key=tag_sort_key)

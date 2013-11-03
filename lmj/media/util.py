import datetime
import json


def parse(x):
    return json.loads(x)


def stringify(x):
    h = lambda z: z.isoformat() if isinstance(z, datetime.datetime) else None
    return json.dumps(x, default=h)


def normalized_tag_set(seq, sep=None):
    '''Return a normalized set of tags from the given sequence.'''
    if not seq:
        return set()
    if isinstance(seq, str):
        seq = seq.split(sep)
    return set(t.lower().strip() for t in seq if t.strip())

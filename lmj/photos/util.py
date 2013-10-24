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
        return []
    if isinstance(seq, str):
        seq = seq.split(sep)
    return set(t.lower().strip() for t in seq if t.strip())


def tags_from_exif(exif):
    '''Given an exif data structure, extract a set of tags.'''
    if not exif:
        return []

    def highest(n, digits=1):
        '''Return n rounded to the top `digits` digits.'''
        n = float(n)
        if n < 10 ** digits:
            return int(n)
        shift = 10 ** (len(str(int(n))) - digits)
        return int(shift * round(n / shift))

    tags = set()

    if 'FNumber' in exif:
        tags.add('f/{}'.format(round(2 * float(exif['FNumber'])) / 2))

    if 'ISO' in exif:
        iso = int(exif['ISO'])
        tags.add('iso:{}'.format(highest(iso, 1 + int(iso > 1000))))

    if 'ShutterSpeed' in exif:
        s = exif['ShutterSpeed']
        n = -1
        if isinstance(s, (float, int)):
            n = int(1000 * s)
        elif s.startswith('1/'):
            n = int(1000. / float(s[2:]))
        else:
            raise ValueError('cannot parse ShutterSpeed "{}"'.format(s))
        tags.add('{}ms'.format(max(1, highest(n))))

    if 'FocalLength' in exif:
        tags.add('{}mm'.format(highest(exif['FocalLength'][:-2])))

    if 'Model' in exif:
        t = exif['Model'].lower()
        for s in 'canon nikon kodak digital camera super ed is'.split():
            t = t.replace(s, '').strip()
        if t:
            tags.add('kit:{}'.format(t))

    return normalized_tag_set(tags)

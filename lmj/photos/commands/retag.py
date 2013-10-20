import datetime
import lmj.cli
import lmj.photos
import os
import sys
import traceback

cmd = lmj.cli.add_command('retag')
cmd.add_argument('--replace', action='store_true',
                 help='replace existing tags')
cmd.add_argument('--add', default=[], nargs='+', metavar='TAG',
                 help='add these TAGs to all selected photos')
cmd.add_argument('tag', nargs='+', metavar='TAG',
                 help='retag only photos with these TAGs')
cmd.set_defaults(mod=sys.modules[__name__])

logging = lmj.cli.get_logger(__name__)


def main(args):
    photos = list(lmj.photos.find_tagged(args.tag))
    for p in photos:
        tags = list(args.add)

        if not args.replace:
            tags.extend(p.user_tag_set)

        tags.append(os.path.basename(os.path.dirname(p.path)))

        if 'FNumber' in p.exif:
            tags.append('f/{}'.format(int(float(p.exif['FNumber']))))

        if 'ISO' in p.exif:
            tags.append('iso{}'.format(p.exif['ISO']))

        if 'ShutterSpeed' in p.exif:
            s = p.exif['ShutterSpeed']
            n = -1
            if isinstance(s, (float, int)):
                n = int(1000 * s)
            elif s.startswith('1/'):
                n = int(1000. / float(s[2:]))
            else:
                raise ValueError('cannot parse ShutterSpeed "{}"'.format(s))
            n -= n % (10 ** (len(str(n)) - 1))
            tags.append('{}ms'.format(max(1, n)))

        if 'FocalLength' in p.exif:
            n = int(float(p.exif['FocalLength'][:-2]))
            n -= n % (10 ** (len(str(n)) - 1))
            tags.append('{}mm'.format(n))

        if 'Model' in p.exif:
            t = p.exif['Model'].lower()
            for make in ('canon', 'nikon', 'kodak', 'digital camera'):
                t = t.replace(make, '').strip()
            tags.append(t)

        p.meta['tags'] = sorted(
            set([t.strip().lower() for t in tags if t.strip()]))

        logging.info('%s: tags: %s',
                     os.path.basename(p.path),
                     ', '.join(p.meta['tags']))

        lmj.photos.update(p)

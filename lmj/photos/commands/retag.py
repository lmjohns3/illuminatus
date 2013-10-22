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
        tags.append(os.path.basename(os.path.dirname(p.path)))
        tags.extend(p.exif_tag_set)
        if not args.replace:
            tags.extend(p.user_tag_set)

        p.meta['tags'] = sorted(
            set([t.strip().lower() for t in tags if t.strip()]))

        logging.info('%s: tags: %s',
                     os.path.basename(p.path),
                     ', '.join(p.meta['tags']))

        lmj.photos.update(p)

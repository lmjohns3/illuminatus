import climate
import datetime
import illuminatus
import os
import sys

cmd = climate.add_command('retag')
cmd.add_argument('--replace', action='store_true',
                 help='replace existing tags')
cmd.add_argument('--exif', action='store_true',
                 help='reload and replace EXIF tags from source')
cmd.add_argument('--add', default=[], nargs='+', metavar='TAG',
                 help='add these TAGs to all selected photos')
cmd.add_argument('--add-path-tag', action='store_true',
                 help='use the parent DIR as a tag for each import')
cmd.add_argument('tag', nargs='+', metavar='TAG',
                 help='retag only photos with these TAGs')
cmd.set_defaults(mod=sys.modules[__name__])

logging = climate.get_logger(__name__)


def main(args):
    photos = list(illuminatus.db.find_tagged(args.tag))
    for p in photos:
        tags = list(args.add)
        if args.add_path_tag:
            tags.append(os.path.basename(os.path.dirname(p.path)))
        if not args.replace:
            tags.extend(p.user_tag_set)

        p.meta['user_tags'] = sorted(illuminatus.util.normalized_tag_set(tags))
        if args.exif:
            p.meta['exif_tags'] = sorted(p.read_exif_tags())

        logging.info('%s: user: %s; exif: %s',
                     os.path.basename(p.path),
                     ', '.join(p.meta['user_tags']),
                     ', '.join(p.meta['exif_tags']),
                     )

        illuminatus.db.update(p)

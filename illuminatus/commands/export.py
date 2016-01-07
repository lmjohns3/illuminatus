import climate
import sys

from illuminatus import db, export

cmd = climate.add_command('export')
cmd.add_argument('--output', metavar='FILE',
                 help='save export zip to FILE')
cmd.add_argument('--include', default=[], nargs='+', metavar='TAG',
                 help='include media tagged with TAG')
cmd.add_argument('--exclude', default=[], nargs='+', metavar='TAG',
                 help='exclude media tagged with TAG')
cmd.add_argument('--hide-tags', default=[], nargs='+', metavar='PATTERN',
                 help='do not export info for tags matching PATTERN')
cmd.add_argument('--show-datetime-tags', default=False, action='store_true',
                 help='include tags related to date data')
cmd.add_argument('--show-exif-tags', default=False, action='store_true',
                 help='include tags related to EXIF data')
cmd.add_argument('--show-omnipresent-tags', default=False, action='store_true',
                 help='do not remove tags that are present in all media')
cmd.add_argument('--size', default=[], type=int, nargs='+', metavar='N',
                 help='export thumbnails bounded by N x N boxes')
cmd.add_argument('--path', default=[], nargs='+', metavar='FILE',
                 help='export FILEs (or load paths from @FILE)')
cmd.set_defaults(mod=sys.modules[__name__])

logging = climate.get_logger(__name__)


def filter_excluded(media, blacklist):
    '''Omit pieces tagged with anything that matches the given pattern.'''
    if not blacklist:
        return list(media)
    logging.info('filtering out %s', blacklist)
    passed = []
    for m in media:
        if not m.tag_set & blacklist:
            passed.append(m)
    return passed


def main(args):
    assert args.size, 'must include at least one --size'

    export.export(
        filter_excluded(db.find(tags=args.include), set(args.exclude)),
        output=args.output,
        sizes=args.size,
        hide_tags=args.hide_tags,
        exif_tags=args.show_exif_tags,
        datetime_tags=args.show_datetime_tags,
        omnipresent_tags=args.show_omnipresent_tags,
    )

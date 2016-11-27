import climate
import datetime
import illuminatus
import os
import sys

cmd = climate.add_command('retag')
cmd.add_argument('--add', default=[], nargs='+', metavar='TAG',
                 help='add these TAGs to all selected photos')
cmd.add_argument('--remove', default=[], nargs='+', metavar='TAG',
                 help='remove these TAGs from all selected photos')
cmd.add_argument('--add-paths', default=0, type=int, metavar='N',
                 help='add the N parent directories as tags')
cmd.add_argument('tag', nargs='+', metavar='TAG',
                 help='retag only media with these TAGs')
cmd.set_defaults(mod=sys.modules[__name__])

logging = climate.get_logger(__name__)


def main(db, args):
    for item in db.select_tagged(args.tag):
        for tag in args.add:
            item.add_tag(tag)
        for tag in args.remove:
            item.remove_tag(tag)
        if args.add_paths > 0:
            components = os.path.dirname(item.path).split(os.sep)[::-1]
            for i in range(args.add_paths):
                tags.append(components[i])

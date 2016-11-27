import climate
import datetime
import fnmatch
import illuminatus
import os
import sys
import traceback

cmd = climate.add_command('ls')
cmd.add_argument('-a', '--after', metavar='DATE',
                 help='show only media from after DATE')
cmd.add_argument('-b', '--before', metavar='DATE',
                 help='show only media from before DATE')
cmd.add_argument('-j', '--json', action='store_true',
                 help='display results as JSON')
cmd.add_argument('-p', '--path', metavar='PATH',
                 help='show only media matching this PATH')
cmd.add_argument('-t', '--tag', nargs='+', metavar='TAG',
                 help='show only media with these TAGs')
cmd.set_defaults(mod=sys.modules[__name__])

logging = climate.get_logger(__name__)


def main(db, args):
    pieces = db.select(after=args.after,
                       before=args.before,
                       path=args.path,
                       tags=args.tag or ())
    if args.json:
        print(illuminatus.util.stringify([p.to_dict() for p in pieces]))
        return
    for item in items:
        stamp = item.stamp.strftime('%Y-%m-%dT%H:%M:%S')
        tags = ' | '.join(item.tags)
        print('{}  {}  {}'.format(stamp, item.path, tags))

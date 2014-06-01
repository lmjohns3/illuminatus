import climate
import datetime
import lmj.media
import os
import sys
import traceback

cmd = climate.add_command('ls')
cmd.add_argument('tag', nargs='+', metavar='TAG',
                 help='show only photos with these TAGs')
cmd.set_defaults(mod=sys.modules[__name__])

logging = climate.get_logger('lmj.media.ls')


def main(args):
    for p in lmj.media.db.find_tagged(args.tag):
        logging.info('%s %s', '|'.join(sorted(p.tag_set)), p.path)

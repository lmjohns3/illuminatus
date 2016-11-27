import climate
import multiprocessing as mp
import sys

cmd = climate.add_command('rethumb')
cmd.add_argument('tag', nargs='+', metavar='TAG',
                 help='retag only photos with these TAGs')
cmd.set_defaults(mod=sys.modules[__name__])

logging = climate.get_logger(__name__)


def thumb(item):
    item.save()
    logging.info(item.path)


def main(db, args):
    mp.Pool().imap_unordered(thumb, db.select_tagged(*args.tag))

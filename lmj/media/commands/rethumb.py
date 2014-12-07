import climate
import lmj.media
import multiprocessing as mp
import sys

cmd = climate.add_command('rethumb')
cmd.add_argument('tag', nargs='+', metavar='TAG',
                 help='retag only photos with these TAGs')
cmd.set_defaults(mod=sys.modules[__name__])

logging = climate.get_logger('lmj.media.rethumb')


def thumb(m):
    '''Generate thumbnails for a single piece of media.'''
    m.make_thumbnails()
    logging.info(m.path)


def main(args):
    mp.Pool().imap_unordered(thumb, lmj.media.db.find(tags=args.tag or []))

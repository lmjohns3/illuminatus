import climate
import lmj.media
import multiprocessing as mp
import sys

cmd = climate.add_command('rethumb')
cmd.add_argument('tag', nargs='+', metavar='TAG',
                 help='retag only photos with these TAGs')
cmd.set_defaults(mod=sys.modules[__name__])

logging = climate.get_logger('lmj.media.rethumb')


def process(queue):
    '''Process media from a workqueue until there is no more work.'''
    while True:
        m = queue.get()
        if m is None:
            break
        m.make_thumbnails()
        logging.info(m.path)


def main(args):
    queue = mp.Queue()
    workers = [mp.Process(target=process, args=(queue, ))
               for _ in range(args.workers)]
    [w.start() for w in workers]
    for m in lmj.media.db.find_tagged(args.tag):
        queue.put(m)
    [queue.put(None) for _ in workers]
    [w.join() for w in workers]

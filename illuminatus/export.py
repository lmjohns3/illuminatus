import climate
import collections
import io
import multiprocessing as mp
import os
import re
import zipfile

from illuminatus.util import stringify, tag_class

logging = climate.get_logger(__name__)


def serialize(work, results):
    while True:
        job = work.get()
        if job is None:
            break
        m, s = job
        logging.info('%s: exporting, size %s', m.path, s)
        results.put((m, s, m.serialize(s)))


def export(media,
           output,
           sizes,
           hide_tags=(),
           exif_tags=False,
           datetime_tags=False,
           omnipresent_tags=False):
    '''Export media to a zip archive.

    The zip archive will contain:

    - A file called index.json, containing a manifest of the exported content.
    - A directory for each "size", containing exported image/movie data files.

    Parameters
    ----------
    media : list of Media
        A list of the media to export.
    output : str or file
        The name of a zip file to save, or a file-like object to write zip
        content to.
    sizes : list of int or list of (int, int)
        A list of sizes to export images and movies to. Each piece of media
        being exported will be resized (if needed) to fit inside a box of the
        given dimensions.
    hide_tags : list of str, optional
        A list of regular expressions matching tags to be excluded from the
        export information. For example, '^a' will exclude all tags starting
        with the letter "a". Default is to export all tags.
    exif_tags : bool
        If True, export tags derived from EXIF data (e.g., ISO:1000, f/2, etc.)
        The default is not to export this information.
    datetime_tags : bool
        If True, export tags derived from time information (e.g., November,
        10am, etc.). The default is not to export this information.
    omnipresent_tags : bool
        If True, export tags present in all media. By default, tags that are
        present in all media being exported will not be exported.
    '''
    logging.info('exporting %d items', len(media))

    # set up a function to get visible tags for a piece.
    hide_pattern = '^{}$'.format('|'.join(hide_tags))
    logging.info('hiding tags matching %s', hide_pattern)
    def visible_tags(m):
        ts = m.user_tag_set
        if exif_tags:
            ts |= m.exif_tag_set
        if datetime_tags:
            ts |= m.datetime_tag_set
        return (t for t in ts if not re.match(hide_pattern, t))

    # count tag usage for this set of media.
    tag_counts = collections.defaultdict(int)
    for m in media:
        for t in visible_tags(m):
            tag_counts[t] += 1

    if not omnipresent_tags:
        # remove tags that are applied to all media pieces.
        omnipresent = [t for t, c in tag_counts.items() if c == len(media)]
        for t in omnipresent:
            del tag_counts[t]
        hide_pattern = '{}$'.format('|'.join(hide_tags + omnipresent))

    logging.info('%d unique tags', len(tag_counts))

    wq = mp.Queue()
    rq = mp.Queue()
    workers = [mp.Process(target=serialize, args=(wq, rq))
               for _ in range(mp.cpu_count())]
    [w.start() for w in workers]

    pieces = []
    for m in media:
        pieces.append(dict(
            stamp=m.stamp,
            img=os.path.basename(m.thumb_path),
            tags=list(visible_tags(m))))
        for s in sizes:
            wq.put((m, s))

    [wq.put(None) for w in workers]

    with zipfile.ZipFile(output, 'w') as zf:
        for _ in range(len(pieces) * len(sizes)):
            m, s, b = rq.get()
            zf.writestr('{}/{:08x}.{}'.format(s, m.id, m.EXTENSION), b)
        zf.writestr('index.json', stringify(dict(
            sizes=sizes, pieces=pieces,
            tags=[dict(name=t, count=c, cls=tag_class(t))
                  for t, c in tag_counts.items()])))

    [w.join() for w in workers]

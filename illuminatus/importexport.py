import click
import collections
import glob
import multiprocessing as mp
import os
import re
import sys
import tempfile
import ujson
import zipfile

from .media import Asset, Tag, medium_for


def _process(jobs_queue, callback):
    while True:
        job = jobs_queue.get()
        if job is None:
            break
        callback(job)


def run_workqueue(jobs, callback, num_workers=mp.cpu_count()):
    jobs_queue = mp.Queue()
    workers = [mp.Process(target=_process, args=(jobs_queue, callback))
               for _ in range(num_workers)]
    [w.start() for w in workers]
    for job in jobs:
        jobs_queue.put(job)
    [jobs_queue.put(None) for w in workers]
    try:
        [w.join() for w in workers]
    except:
        # empty the jobs queue to force workers to halt.
        while not jobs_queue.empty():
            jobs_queue.get(False)
        raise
    finally:
        [w.terminate() for w in workers]


class Importer:
    '''A class for importing media into the database.

    Parameters
    ----------
    db : str
        Filesystem path for our database.
    tags : list of str
        Extra tags to add to all imported assets.
    path_tags : int
        Number of parent directory names to add as tags for each imported asset.
    '''

    def __init__(self, session, tags, path_tags):
        self.session = session
        self.tags = tags
        self.path_tags = path_tags

    def walk(self, roots):
        '''Recursively visit all files under the given root directories.

        Parameters
        ----------
        roots : sequence of str
            Root paths to search for files.

        Yields
        ------
        Filenames under each of the given root paths.
        '''
        for src in roots:
            for match in glob.glob(src):
                match = os.path.abspath(match)
                if os.path.isdir(match):
                    for base, dirs, files in os.walk(match):
                        dots = [n for n in dirs if n.startswith('.')]
                        [dirs.remove(d) for d in dots]
                        for name in files:
                            if not name.startswith('.'):
                                yield os.path.abspath(os.path.join(base, name))
                else:
                    yield match

    def run(self, roots):
        '''Run the import process in parallel on the given root paths.

        Parameters
        ----------
        roots : sequence of str
            Root paths to search for files.
        '''
        run_workqueue(self.walk(roots), self.import_one)

    def import_one(self, path):
        '''Import a single path into the media database.

        Parameters
        ----------
        path : str
            A filesystem path to examine and possibly import.
        '''
        try:
            with self.session() as sess:
                if sess.query(Asset).filter(Asset.path == path).count():
                    click.echo('{} Already have {}'.format(
                        click.style('=', fg='blue'),
                        click.style(path, fg='red')))
                    return
                medium = medium_for(path)
                if medium is None:
                    click.echo('{} Unknown {}'.format(
                        click.style('?', fg='yellow'),
                        click.style(path, fg='red')))
                    return
                asset = Asset(path=path, medium=medium)
                for tag in self.tags:
                    asset.increment_tag(tag)
                components = os.path.dirname(path).split(os.sep)[::-1]
                for i in range(self.path_tags):
                    asset.increment_tag(components[i])
                sess.add(asset)
                click.echo('{} Added {}'.format(
                        click.style('+', fg='green'),
                        click.style(path, fg='red')))
        except KeyboardInterrupt:
            pass
        except:
            _, exc, tb = sys.exc_info()
            click.echo('! Error {} {}'.format(path, exc))  # , ''.join(tb))


class Thumbnailer:
    '''Export thumbnails of media content to files on disk.

    Parameters
    ----------
    assets : list of :class:`Asset`
        A list of the media assets to thumbnail.
    root : str
        A filesystem path for saving thumbnails.
    overwrite : bool
        If True, we'll overwrite existing thumbnails.
    audio_format : :class:`Format`
        A Format for audio thumbnails.
    photo_format : :class:`Format`
        A Format for photo thumbnails.
    video_format : :class:`Format`
        A Format for video thumbnails.
    '''

    def __init__(self, assets, root=None, overwrite=False, audio_format=None,
                 video_format=None, photo_format=None):
        self.assets = assets
        self.root = root
        self.overwrite = overwrite
        self.audio_format = audio_format
        self.photo_format = photo_format
        self.video_format = video_format

    def run(self):
        '''Export thumbnails for media to files on disk.'''
        run_workqueue(self.assets, self)

    def __call__(self, asset):
        fmt = getattr(self, '{}_format'.format(asset.medium.name.lower()))
        if fmt is None:
            return
        output = asset.export(fmt=fmt, root=self.root, overwrite=self.overwrite)
        if output is None:
            return
        click.echo('{} {} -> {}'.format(click.style('T', fg='cyan'),
                                        click.style(asset.path, fg='red'),
                                        click.style(output, fg='green')))


class Exporter:
    '''Export media content to a zip file on disk.

    Parameters
    ----------
    all_tags : list of :class:`Tag`
        All tags defined in the database.
    assets : list of :class:`Asset`
        A list of the media assets to export.
    audio_format : :class:`Format`
        A Format for audio thumbnails.
    photo_format : :class:`Format`
        A Format for photo thumbnails.
    video_format : :class:`Format`
        A Format for video thumbnails.
    '''

    def __init__(self, all_tags, assets, audio_format=None, video_format=None,
                 photo_format=None):
        self.all_tags = all_tags
        self.assets = assets
        self.audio_format = audio_format
        self.photo_format = photo_format
        self.video_format = video_format

    def run(self, output, hide_tags=(), hide_metadata_tags=False,
            hide_datetime_tags=False, hide_omnipresent_tags=False):
        '''Export media to a zip archive.

        The zip archive will contain:

        - A file called index.json, containing a manifest of exported content.
        - A directory for each size, containing exported media data files.

        Parameters
        ----------
        output : str or file
            The name of a zip file to save, or a file-like object to write zip
            content to.
        hide_tags : list of str, optional
            A list of regular expressions matching tags to be excluded from the
            export information. For example, '^a' will exclude all tags
            starting with the letter "a". Default is to export all tags.
        hide_metadata_tags : bool, optional
            If True, export tags derived from EXIF data (e.g., ISO:1000, f/2,
            etc.) The default is not to export this information.
        hide_datetime_tags : bool, optional
            If True, export tags derived from time information (e.g., November,
            10am, etc.). The default is not to export this information.
        hide_omnipresent_tags : bool, optional
            If True, export tags present in all media. By default, tags that
            are present in all assets being exported will not be exported.
        '''
        hide_patterns = list(hide_tags)
        if hide_metadata_tags:
            hide_patterns.append(Tag.METADATA_PATTERN)
        if hide_datetime_tags:
            hide_patterns.append(Tag.DATETIME_PATTERN)

        hide_names = set()
        for pattern in hide_patterns:
            for tag in self.all_tags:
                if re.match(pattern, tag.name):
                    hide_names.add(tag.name)
        if hide_omnipresent_tags:
            # count tag usage for this set of assets.
            tag_counts = collections.defaultdict(int)
            for asset in self.assets:
                for tag in asset.tags:
                    tag_counts[tag.name] += 1
            # remove tags that are applied to all assets.
            for name, count in tag_counts.items():
                if count == len(self.assets):
                    hide_names.add(name)

        with tempfile.TemporaryDirectory() as root:
            index = os.path.join(root, 'index.json')
            self.root = root
            run_workqueue(self.assets, self)
            with open(index, 'w') as handle:
                ujson.dump([asset.to_dict(exclude_tags=hide_names)
                            for asset in self.assets], handle)
            _create_zip(output, root)

        return len(self.assets)

    def __call__(self, asset):
        fmt = getattr(self, '{}_format'.format(asset.medium.name.lower()))
        if fmt is not None:
            asset.export(fmt=fmt, root=self.root)


# This is mostly from zipfile.py in the Python source.
def _create_zip(output, root):
    def add(zf, path, zippath):
        if os.path.isfile(path):
            zf.write(path, zippath, zipfile.ZIP_DEFLATED)
        elif os.path.isdir(path):
            for x in os.listdir(path):
                add(zf, os.path.join(path, x), os.path.join(zippath, x))
    with zipfile.ZipFile(output, 'w') as zf:
        add(zf, root, os.path.splitext(os.path.basename(output))[0])

import base64
import click
import collections
import glob
import hashlib
import mimetypes
import os
import re
import tempfile
import zipfile

from .assets import Asset, Format
from .tags import Tag


def walk(roots):
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


def _guess_medium(path):
    '''Determine the appropriate medium for a given path.

    Parameters
    ----------
    path : str
        Filesystem path where the asset is stored.

    Returns
    -------
    A string naming an asset medium. Returns None if no known media types
    handle the given path.
    '''
    mime, _ = mimetypes.guess_type(path)
    for pattern, medium in (('audio/.*', Asset.Medium.Audio),
                            ('video/.*', Asset.Medium.Video),
                            ('image/.*', Asset.Medium.Photo)):
        if re.match(pattern, mime):
            return medium
    return None


def import_asset(sess, path, tags=(), path_tags=0):
    '''Import a single asset into the database.

    Parameters
    ----------
    sess : db.Session
        Database session for the import.
    path : str
        A filesystem path to examine and possibly import.
    tags : set of str
        Tags to add to this asset.
    path_tags : int
        Number of path (directory) name components to add as tags.
    '''
    digest = hashlib.blake2s(path.encode('utf-8')).digest()
    slug = base64.b64encode(digest, b'-_').strip(b'=').decode('utf-8')
    match = Asset.slug == slug

    if sess.query(Asset).filter(match).count():
        click.echo('{} Already have {}'.format(
            click.style('=', fg='blue'),
            click.style(path, fg='red')))
        return None

    medium = _guess_medium(path)
    if medium is None:
        click.echo('{} Unknown {}'.format(
            click.style('?', fg='yellow'),
            click.style(path, fg='red')))
        return None

    tags = set(tags)
    components = os.path.dirname(path).split(os.sep)[::-1]
    for i in range(min(len(components) - 1, path_tags)):
        tags.add(components[i])

    asset = Asset(path=path, medium=medium, slug=slug)
    for tag in tags:
        asset.tags.add(tag)
    sess.add(asset)

    click.echo('{} Added {}'.format(
            click.style('+', fg='green'),
            click.style(path, fg='red')))

    return asset


def export(assets, all_tags, formats, output,
           hide_tags=(),
           hide_metadata_tags=False,
           hide_datetime_tags=False,
           hide_omnipresent_tags=False):
    '''Export media to a zip archive.

    The zip archive will contain:

    - A file called index.json, containing a manifest of exported content.
    - A directory for each size, containing exported media data files.

    Parameters
    ----------
    assets : list of :class:`db.Asset`
        A list of the assets to export.
    all_tags : list of :class:`db.Tag`
        All tags defined in the database.
    formats : list of dict
        The formats that we should use for the export.
    output : str or file
        The name of a zip file to save, or a file-like object to write zip
        content to.
    hide_tags : list of str, optional
        A list of regular expressions matching tags to be excluded from the
        export information. For example, 'a.*' will exclude all tags
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
        for tag in all_tags:
            if re.match(pattern, tag.name):
                hide_names.add(tag.name)
    if hide_omnipresent_tags:
        # count tag usage for this set of assets.
        tag_counts = collections.defaultdict(int)
        for asset in assets:
            for tag in asset.tags:
                tag_counts[tag.name] += 1
        # remove tags that are applied to all assets.
        for name, count in tag_counts.items():
            if count == len(assets):
                hide_names.add(name)

    with tempfile.TemporaryDirectory() as root:
        index = os.path.join(root, 'index.json')
        data = []
        for asset in assets:
            for fmt in formats:
                if fmt.medium.lower() == asset.medium.name.lower():
                    path = root
                    if 'path' in fmt:
                        path = os.path.join(path, fmt['path'])
                    asset.export(path, Format(**fmt['format']))
            data.append(asset.to_dict(exclude_tags=hide_names))
        with open(index, 'w') as handle:
            json.dump(data, handle)
        _create_zip(output, root)

    return len(assets)


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

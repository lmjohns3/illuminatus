import click
import os
import sys

from .db import DB
from .media import Tag, Format, Audio, Photo, Video
from .importexport import Importer, Exporter, Thumbnailer


@click.group()
@click.option('--db', envvar='ILLUMINATUS_DB', metavar='PATH',
              help='Load illuminatus database from PATH.')
@click.pass_context
def cli(ctx, db, **kwargs):
    '''Command-line interface for media management.'''
    # Don't require a database for getting help.
    if ctx.invoked_subcommand == 'query' or '--help' in sys.argv:
        return

    if not db:
        raise click.UsageError('no --database specified!')

    ctx.obj = dict(db=db)


@cli.command()
@click.pass_context
def query(ctx):
    '''
    Illuminatus queries permit a wide range of media selection, expressed using
    a set notation. The query syntax understands the following sets of media:

    \b
    - TAG -- media that are tagged with TAG
    - before:YYYY-MM-DD -- media with timestamps on or before YYYY-MM-DD
    - after:YYYY-MM-DD -- media with timestamps on or after YYYY-MM-DD
    - path:STRING -- media whose source path contains the given STRING

    Each pair of terms in a query is combined using one of the three set
    operators:

    \b
    - X & Y -- media in set X and in set Y
    - X | Y -- media in set X or set Y
    - X ~ Y -- media in set X but not in set Y

    Finally, parentheses can be used in the usual way, to group operations.

    \b
    Examples
    --------

    \b
    - cake
      selects everything tagged "cake"
    - cake ~ ice-cream
      selects everything tagged "cake" that is not also tagged "ice-cream"
    - cake & ice-cream
      selects everything tagged with both "cake" and "ice-cream"
    - cake & before:2010-03-14
      selects everything tagged "cake" from before pi day 2010
    - cake & (before:2010-03-14 | after:2011-03-14)
      selects everything tagged "cake" that wasn't between pi day 2010 and
      pi day 2011
    '''
    print(ctx.get_help())


@cli.command()
@click.pass_context
def spec(ctx):
    '''
    Illuminatus can export media in a variety of output formats. To specify
    which format you'd like to use for output, provide one or more format
    specifications using the --audio-format, --photo-format and
    --video-format flags. Each specification can include the following

    \b
    Audio
    -----
    - ext: Output filename extension.
    - fps: Frames per second when exporting audio or video.
    - channels [1]: Number of channels in exported audio files.

    Examples

    - fps=8000
      export audio clips as AAC at 8kHz -- this is the shortest way of
      specifying an audio format

    \b
    Photo
    -----
    - ext: Output filename extension.
    - bbox: Maximum size of the output images.

    Examples

    - 100
      export photos as jpg scaled down to fit inside a 100x100 box -- this is
      the shortest way of specifying a photo format
    - ext=jpg,bbox=100x100
      same as above, giving explicit option names

    \b
    Video
    -----
    - ext: Output filename extension.
    - bbox: Maximum size of the output frames.
    - fps: Frames per second when exporting audio or video.
    - palette [255]: Number of colors in the palette for exported animated GIFs.
    - vcodec [libx264]: Codec to use for exported video.
    - acodec [aac]: Codec to use for audio in exported videos.
    - abitrate [128k]: Bits per second for audio in exported videos.
    - crf [30]: Quality scale for exporting videos.
    - preset [medium]: Speed preset for exporting videos.

    \b
    Examples

    - 100
      exports video as mp4 scaled down to fit inside a 100x100 box -- this is
      the shortest way of specifying a video format
    - ext=mp4,bbox=100x100
      same as above, giving explicit option names for extension and bounding box
    - gif,100,fps=3,palette=64
      exports video as 64-color animated GIFs at 3 frames per second
    '''
    print(ctx.get_help())


@cli.command()
@click.option('--order', default='stamp-', metavar='[stamp|path]',
              help='Sort records by this field. A "-" at the end reverses the order.')
@click.argument('query', nargs=-1)
@click.pass_context
def ls(ctx, query, order):
    '''List media items matching a QUERY.

    See "illuminatus query --help" for help on QUERY syntax.
    '''
    def color(tag):
        return ('cyan' if tag.source == Tag.METADATA else
                'green' if tag.source == Tag.DATETIME else
                'yellow')

    for item in DB(ctx.obj['db']).select(' '.join(query), order=order):
        click.echo('{} {} {}'.format(
            # click.style(item.path_hash, fg='red'),
            click.style(str(item.stamp)),
            ' '.join(click.style(t.name, fg=color(t)) for t in sorted(item.tags)),
            click.style(item.path)))


@cli.command()
@click.option('--hide-original', is_flag=True,
              help='"Delete" the source media file, by renaming it.')
@click.argument('query', nargs=-1)
@click.pass_context
def rm(ctx, query, hide_original):
    '''Remove media matching a QUERY from the database.

    See "illuminatus query --help" for help on QUERY syntax.

    Media that are deleted from the database can additionally be "removed" from
    the filesystem by specifying an extra flag. The "removal" takes place by
    renaming the original source file with an ".illuminatus-removed-" prefix.
    An offline process (e.g., a cron script) can garbage-collect these renamed
    files as needed.
    '''
    for item in DB(ctx.obj['db']).select(' '.join(query)):
        item.delete(hide_original=hide_original)


@cli.command()
@click.option('--output', metavar='FILE', help='save export zip to FILE')
@click.option('--hide-tags', multiple=True, metavar='REGEXP [REGEXP...]',
              help='Exclude tags matching REGEXP from exported items.')
@click.option('--hide-datetime-tags', default=False, is_flag=True,
              help='Include tags related to timestamp data.')
@click.option('--hide-metadata-tags', default=False, is_flag=True,
              help='Include tags from media metadata like EXIF.')
@click.option('--hide-omnipresent-tags', default=False, is_flag=True,
              help='Do not remove tags that are present in all items.')
@click.option('--audio-format', metavar='SPEC', default='abitrate=128k',
              help='Export audio in these formats.')
@click.option('--photo-format', metavar='SPEC', default='800',
              help='Export photos in these formats.')
@click.option('--video-format', metavar='SPEC', default='800',
              help='Export videos in these formats.')
@click.argument('query', nargs=-1)
@click.pass_context
def export(ctx, query, audio_format, photo_format, video_format, **kwargs):
    '''Export a zip file of all media that match a QUERY.

    See "illuminatus query --help" for help on QUERY syntax, and
    "illuminatus spec --help" for help on SPEC syntax.
    '''
    db = DB(ctx.obj['db'])
    Exporter(
        db.tags,
        db.select(' '.join(query)),
        audio_format=Format.parse(audio_format),
        photo_format=Format.parse(photo_format),
        video_format=Format.parse(video_format),
    ).run(**kwargs)


@cli.command('import')
@click.option('--tag', multiple=True, metavar='TAG [TAG...]',
              help='Add TAG to all imported items.')
@click.option('--path-tags', default=0, metavar='N',
              help='Add N parent directories as tags.')
@click.argument('source', nargs=-1)
@click.pass_context
def import_(ctx, source, tag, path_tags):
    '''Import media into the illuminatus database.

    If any SOURCE is a directory, all media under that directory will be
    imported recursively.
    '''
    Importer(ctx.obj['db'], tag, path_tags).run(source)


@cli.command()
@click.option('--stamp', type=str,
              help='Modify the timestamp of matching records.')
@click.option('--add-tag', type=str, multiple=True, metavar='TAG [TAG...]')
@click.option('--remove-tag', type=str, multiple=True, metavar='TAG [TAG...]')
@click.option('--add-path-tags', default=0, metavar='N',
              help='Add N parent directories as tags.')
@click.argument('query', nargs=-1)
@click.pass_context
def modify(ctx, query, stamp, add_tag, remove_tag, add_path_tags):
    '''Modify media items matching a QUERY.

    See "illuminatus query --help" for help on QUERY syntax.

    Common tasks are adding or removing tags, or updating the timestamps
    associated with one or more media items (e.g., to adjust for a
    miscalibrated camera or the like).

    The --stamp option can take two different types of timestamp specifiers.
    If this option is passed a timestamp string, it will replace the current
    timestamp for all matching media. Otherwise it can contain any number
    of strings of the form 'sNx' which will adjust timestamp unit x by
    N units either later (if s is '+') or earlier (if s is '-'). For
    example, '+3y,-2h' will shift the timestamp of all matching media
    three years later and two hours earlier. Here x can be 'y' (year),
    'm' (month), 'd' (day), or 'h' (hour).
    '''
    for item in DB(ctx.obj['db']).select(' '.join(query)):
        for tag in add_tag:
            item.add_tag(tag)
        for tag in remove_tag:
            item.remove_tag(tag)
        if add_path_tags > 0:
            components = os.path.dirname(item.path).split(os.sep)[::-1]
            for i in range(add_path_tags):
                tags.append(components[i])
        if stamp:
            item.update_stamp(stamp)
        item.save()


@cli.command()
@click.option('--thumbnails', metavar='DIR',
              help='Save thumbnails in a directory under DIR.')
@click.option('--audio-format', default='', metavar='SPEC',
              help='Save audio thumbnails in this format.')
@click.option('--photo-format', default='', metavar='SPEC',
              help='Save photo thumbnails in this format.')
@click.option('--video-format', default='', metavar='SPEC',
              help='Save video thumbnails in this format.')
@click.argument('query', nargs=-1)
@click.pass_context
def thumbnail(ctx, query, thumbnails, audio_format, photo_format, video_format):
    '''Generate thumbnails for media items matching a QUERY.

    See "illuminatus query --help" for help on QUERY syntax, and
    "illuminatus spec --help" for help on SPEC syntax.
    '''
    Thumbnailer(
        DB(ctx.obj['db']).select(' '.join(query)),
        root=thumbnails,
        audio_format=Format.parse(audio_format),
        photo_format=Format.parse(photo_format),
        video_format=Format.parse(video_format),
    ).run()


@cli.command()
@click.option('--host', default='localhost', metavar='HOST',
              help='Run server on HOST.')
@click.option('--port', default=5555, metavar='PORT',
              help='Run server on PORT.')
@click.option('--debug/--no-debug', default=False)
@click.option('--hide-originals/--no-hide-originals', default=False)
@click.option('--thumbnails', metavar='PATH',
              help='Absolute PATH for thumbnailed media content.')
@click.option('--small-audio-format', default='', metavar='SPEC',
              help='Format for small audio format "thumbnails".')
@click.option('--small-photo-format', default='', metavar='SPEC',
              help='Format for small photo format "thumbnails".')
@click.option('--small-video-format', default='', metavar='SPEC',
              help='Format for small video format "thumbnails".')
@click.option('--large-audio-format', default='', metavar='SPEC',
              help='Format for large audio format "thumbnails".')
@click.option('--large-photo-format', default='', metavar='SPEC',
              help='Format for large photo format "thumbnails".')
@click.option('--large-video-format', default='', metavar='SPEC',
              help='Format for large video format "thumbnails".')
@click.pass_context
def serve(ctx, host, port, debug, hide_originals, thumbnails, **kwargs):
    '''Start an HTTP server for media metadata.'''
    classes = dict(audio=Audio, photo=Photo, video=Video)
    from .serve import app
    app.config['db'] = DB(ctx.obj['db'])
    fmts = app.config['formats'] = {}
    for key, value in kwargs.items():
        cls = classes[key.split('_')[1]]
        fmt = Format.parse(value)
        fmts[key] = dict(path=str(fmt), ext=fmt.ext or cls.EXTENSION)
    app.config['thumbnails'] = thumbnails
    app.config['hide-originals'] = hide_originals
    app.run(host=host, port=port, debug=debug, threaded=True)

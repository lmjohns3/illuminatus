import click
import contextlib
import os
import re
import sys
import time
import torch
import yaml

from . import celery
from . import classifier
from . import db
from . import importexport
from . import query

from .assets import Asset
from .tags import Tag


@contextlib.contextmanager
def transaction():
    '''Run a database session with proper setup and cleanup.'''
    sess = db.Session()
    try:
        yield sess
        sess.commit()
    except:
        sess.rollback()
        raise
    finally:
        sess.close()


def normalize_path(p):
    return os.path.abspath(os.path.expandvars(os.path.expanduser(p)))


query_assets = query.assets


def matching_assets(q, **kwargs):
    '''Get assets matching a query, using a local session (i.e., read-only).'''
    with transaction() as sess:
        yield from query_assets(sess, q, **kwargs)


def progressbar(items, label):
    '''Show a progress bar using the given items and label.'''
    items = list(items)
    kwargs = dict(length=len(items), label=label, width=0, fill_char='█')
    with click.progressbar(**kwargs) as bar:
        while items:
            done = []
            try:
                done.extend(i for i, item in enumerate(items) if item.ready())
            except:
                pass
            for i in reversed(done):
                items.pop(i)
                bar.update(1)
            time.sleep(1)


@click.group()
@click.option('--config', metavar='FILE',
              help='Load YAML configuration from FILE.')
@click.option('--log-sql/--no-log-sql', default=False,
              help='Log database queries.')
@click.option('--log-tools/--no-log-tools', default=False,
              help='Log tool commands.')
@click.pass_context
def cli(ctx, config, log_sql, log_tools):
    '''Command-line interface for media database.'''
    # Don't require a database for getting help.
    if ctx.invoked_subcommand == 'help' or '--help' in sys.argv:
        return

    if ctx.invoked_subcommand != 'init':
        if not os.path.isfile(config):
            raise RuntimeError('Illuminatus config not found: {}'.format(
                click.style(config, fg='cyan')))

    with open(config) as handle:
        parsed = yaml.load(handle, Loader=yaml.CLoader)

    for key in ('db', 'thumbnails', 'trash'):
        if key in parsed:
            parsed[key] = normalize_path(parsed[key])

    ctx.obj = dict(config=config, log_sql=log_sql, **parsed)

    # Configure sqlalchemy sessions to connect to our database.
    db.Session.configure(bind=db.engine(path=parsed['db'], echo=log_sql))
    celery.app.conf.update(illuminatus_db=parsed['db'])

    if log_tools:
        from . import ffmpeg
        ffmpeg._DEBUG = 1


@cli.command()
@click.pass_context
def help(ctx):
    '''Help on QUERYs.

    \b
    Queries
    =======

    Queries permit a wide range of media selection, expressed using a set
    notation. The query syntax understands the following sets of media:

    \b
    - TAG -- assets that are tagged with TAG
    - before:YYYY-MM-DD -- assets with timestamps on or before YYYY-MM-DD
    - during:YYYY-MM -- assets with timestamps in the range YYYY-MM
    - after:YYYY-MM-DD -- assets with timestamps on or after YYYY-MM-DD
    - path:STRING -- assets whose source path contains the given STRING
    - hash:STRING -- assets whose hash contains the given STRING
    - audio/photo/video -- assets that are audio, photo, or video

    Each of the terms in a query is combined using one of the three set
    operators:

    \b
    - X Y -- media in set X and in set Y
    - X or Y -- media in set X or set Y
    - not Y -- media not in set Y

    Finally, parentheses can be used in the usual way, to group operations.

    \b
    Examples
    --------

    \b
    - cake
      selects everything tagged "cake"
    - cake not ice-cream
      selects everything tagged "cake" that is not also tagged "ice-cream"
    - cake ice-cream
      selects everything tagged with both "cake" and "ice-cream"
    - cake before:2010-03-14
      selects everything tagged "cake" from before pi day 2010
    - cake (before:2010-03-14 or after:2011-03-14)
      selects everything tagged "cake" that wasn't between pi day 2010 and
      pi day 2011
    '''
    print(ctx.get_help())


DEFAULT_CONFIG = '''\
db: {db}
thumbnails: {thumbs}
{trash}

formats:
  photo:
    thumb: {ext: png, bbox: [320, 320]}
    full: {ext: jpg, bbox: [1080, 1080]}
  video:
    thumb: {ext: webp, bbox: [320, 320], fps: 6}
    full: {ext: webm, bbox: [1080, 1080], fps: 24}
  audio:
    thumb: {ext: png, bbox: [320, 320]}
    full: {ext: mp3, abr: 100}

tags:
- group: date
  icon: 🗓
  patterns: [
    /^(19|20)\d\d$/,
    january, february, march, april, may, june,
    july, august, september, october, november, december,
    /^\d(st|nd|rd|th)$/, /^\d\d(st|nd|rd|th)$/,
    sunday, monday, tuesday, wednesday, thursday, friday, saturday ]

- group: time
  icon: ⌚
  patterns: [
    12am, /^\dam$/, /^\d\dam$/, 12pm, /^\dpm$/, /^\d\dpm$/ ]

- group: kit
  icon: 📷
  patterns: [
    /^kit-\S+$/,
    /^ƒ-\d$/, /^ƒ-\d\d$/, /^ƒ-\d\d\d$/,
    /^\dmm$/, /^\d\dmm$/, /^\d\d\dmm$/, /^\d\d\d\dmm$/ ]

- group: other
  icon: 🏷️
  patterns: [/^.*$/]
'''

@cli.command()
@click.option('--thumbnails', default='', metavar='DIR',
              help=('Store thumbnails under DIR. Defaults to "thumbs" in '
                    'the same location as the database.'))
@click.option('--trash', default='', metavar='DIR',
              help='Storage for deleted assets.')
@click.argument('db_path', default='illuminatus.db', metavar='FILE')
@click.pass_context
def init(ctx, db_path, thumbnails, trash):
    '''Initialize a new illuminatus database and configuration.'''
    db.Model.metadata.create_all(db.engine(db_path))
    if not thumbnails:
        thumbnails = os.path.join(os.path.dirname(db_path), 'thumbs')
    print(DEFAULT_CONFIG.format(db=db_path,
                                thumbnails=thumbnails,
                                trash=f'trash: {trash}' if trash else ''))


def display(asset, include_tags='.*', exclude_tags=None):
    tags = sorted((t for t in asset._tags if re.match(include_tags, t.name)),
                  key=lambda t: (t.pattern, t.name))
    yield asset.slug
    yield ' '.join(sorted(str(h) for h in asset.hashes if len(h.nibbles) < 10))
    yield ' '.join(str(t) for t in tags)
    yield click.style(asset.path)


@cli.command()
@click.option('--order', default='stamp-', metavar='[stamp|path]',
              help='Sort records by this field. A "-" at the end reverses the order.')
@click.option('--limit', default=0, metavar='N', help='Limit to N records.')
@click.argument('query', nargs=-1)
@click.pass_context
def ls(ctx, query, order, limit):
    '''List assets matching a QUERY.

    See "illuminatus help" for help on QUERY syntax.
    '''
    for asset in matching_assets(query, order=order, limit=limit):
        click.echo(' '.join(display(asset)))


@cli.command()
@click.option('--method', default='dhash-8', metavar='[dhash-8|rgb-16|...]',
              help='Check for asset neighbors using this hashing method.')
@click.option('--max-distance', default=1, metavar='R',
              help='Look for neighbors with at most R changed bits.')
@click.argument('query', nargs=-1)
@click.pass_context
def dupe(ctx, query, method, max_distance):
    '''List duplicate assets matching a QUERY.

    See "illuminatus help" for help on QUERY syntax.
    '''
    with transaction() as sess:
        for asset in query_assets(sess, query):
            neighbors = asset.dupes(sess, method, max_distance)
            if neighbors:
                click.echo(' '.join(display(asset)))
                for neighbor in neighbors:
                    click.echo('--> ' + ' '.join(display(neighbor)))
                click.echo('')


@cli.command()
@click.argument('query', nargs=-1)
@click.pass_context
def rm(ctx, query):
    '''Remove assets matching a QUERY.

    See "illuminatus help" for help on QUERY syntax.

    Assets that are deleted from the database can additionally be moved to a
    "trash" folder specified in the config. An offline process (e.g., a cron
    script) can garbage-collect these files as needed.
    '''
    with transaction() as sess:
        for asset in query_assets(sess, query):
            if 'trash' in ctx.obj:
                asset.move_to_trash(ctx.obj['trash'])
            sess.delete(asset)


@cli.command()
@click.option('--output', metavar='FILE', help='Save export zip to FILE.')
@click.option('--hide-tags', multiple=True, metavar='REGEXP [REGEXP...]',
              help='Exclude tags matching REGEXP from exported items.')
@click.option('--hide-omnipresent-tags', default=False, is_flag=True,
              help='Do not remove tags that are present in all items.')
@click.argument('query', nargs=-1)
@click.pass_context
def export(ctx, query, output, hide_tags, hide_omnipresent_tags):
    '''Export a zip file matching a QUERY.

    See "illuminatus help" for help on QUERY syntax.
    '''
    assets = list(matching_assets(query))
    with tempfile.NamedTemporaryDirectory() as root:
        def items():
            for asset in assets:
                yield from asset.export_for_zip(root.name, ctx.obj['formats'])
        progressbar(items(), 'Export')
        importexport.export_zip(
            assets, root.name, output, hide_tags, hide_omnipresent_tags)
    click.echo(output)


@cli.command('import')
@click.option('--tag', multiple=True, metavar='TAG [TAG...]',
              help='Add TAG to all imported items.')
@click.option('--path-tags', default=0, metavar='N',
              help='Add N parent directories as tags.')
@click.argument('source', nargs=-1)
@click.pass_context
def import_(ctx, source, tag, path_tags):
    '''Import assets into the database.

    If any source is a directory, all assets under that directory will be
    imported recursively.
    '''
    def items():
        for path in importexport.walk(source):
            res = importexport.maybe_import_asset(
                db.Session(), path, tag, path_tags)
            if res is not None:
                yield res
    progressbar(items(), 'Metadata')


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
    '''Modify assets matching a QUERY.

    See "illuminatus help" for help on QUERY syntax.

    Common tasks are adding or removing tags, or updating the timestamps
    associated with one or more assets (e.g., to adjust for a
    miscalibrated camera or the like).

    The --stamp option can take two different types of timestamp specifiers.
    If this option is passed a timestamp string, it will replace the current
    timestamp for all matching assets. Otherwise it can contain any number of
    strings of the form 'sNx' which will adjust timestamp unit x by N units
    later (if s is '+') or earlier (if s is '-'). For example, '+3y,-2h' will
    shift the timestamp of all matching media three years later and two hours
    earlier. Here x can be 'y' (year), 'm' (month), 'd' (day), or 'h' (hour).
    '''
    with transaction() as sess:
        for asset in query_assets(sess, query):
            asset.tags -= set(remove_tag)
            for tag in add_tag:
                asset.maybe_add_tag(tag)
            asset.add_path_tags(add_path_tags)
            if stamp:
                asset.update_stamp(stamp)
            sess.add(asset)


@cli.command()
@click.option('--overwrite/--no-overwrite', default=False,
              help='When set, overwrite existing thumbnails.')
@click.argument('query', nargs=-1)
@click.pass_context
def thumbnail(ctx, query, overwrite):
    '''Create thumbnails for assets matching a QUERY.

    See "illuminatus help" for help on QUERY syntax.
    '''
    def items():
        for asset in matching_assets(query):
            yield from asset.export_for_web(
                ctx.obj['thumbnails'],
                ctx.obj['formats'],
                overwrite)
    progressbar(items(), 'Thumbnails')


@cli.command()
@click.option('--feature-tags', type=str, metavar='TAG[,TAG,...]')
@click.option('--label-tags', type=str, metavar='TAG[,TAG,...]')
@click.option('--epochs', default=10, metavar='N', help='Train for N epochs.')
@click.option('--validation-split', default='abcdef', metavar='S[,S,...]',
              help='Use assets with slugs ending in S for model validation.')
@click.option('--save', default=None, metavar='PATH',
              help='After training, save the model to PATH.')
@click.argument('query', nargs=-1)
@click.pass_context
def train(ctx, query, feature_tags, label_tags, epochs, validation_split, save):
    '''Train a classification model on assets matching a QUERY.

    See "illuminatus help" for help on QUERY syntax.
    '''
    def get_tags(tags, filter_fn):
        if tags:
            return tags.split(',')
        with transaction() as sess:
            for t in sess.query(Tag).all():
                if filter_fn(t):
                    yield t.name

    label_tags = sorted(set(get_tags(label_tags, lambda t: t.is_user)))
    print(f'Got {len(label_tags)} label tags.')

    feature_tags = sorted(set(get_tags(feature_tags, lambda t: not t.is_user)))
    print(f'Got {len(feature_tags)} feature tags.')

    if ',' in validation_split:
        validation_split = validation_split.split(',')
    print(f'Got validation split: {validation_split}')

    train, valid = [], []
    for asset in matching_assets('photo not untouched'):
        if any(asset.slug.endswith(s) for s in validation_split):
            valid.append(asset.to_dict())
        else:
            train.append(asset.to_dict())
    print(f'Got {len(train)} training and {len(valid)} validation assets.')

    model = classifier.train(epochs, train, valid, feature_tags, label_tags)
    if save:
        torch.save(dict(model_state=model.state_dict(),
                        feature_tags=feature_tags,
                        label_tags=label_tags), save)


@cli.command()
@click.option('--host', default='localhost', metavar='HOST',
              help='Run server on HOST.')
@click.option('--port', default=5555, metavar='PORT',
              help='Run server on PORT.')
@click.option('--debug/--no-debug', default=False)
@click.option('--slug-size', default=999, metavar='N',
              help='Use only the first N characters from asset slugs.')
@click.pass_context
def serve(ctx, host, port, debug, slug_size):
    '''Start an HTTP server for asset metadata.'''
    from .serve import app
    from .serve import sql
    import multiprocessing

    app.config.update(ctx.obj)
    app.config['SQLALCHEMY_ECHO'] = ctx.obj['log_sql']
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + ctx.obj['db']
    app.config['slug-size'] = slug_size

    sql.init_app(app)

    workers = multiprocessing.cpu_count()
    try:
        _maybe_run_unicorn(app, host, port, debug, workers)
    except ImportError:
        app.run(host=host, port=port, debug=debug, threaded=False,
                processes=workers)


def _maybe_run_unicorn(app, host, port, debug, parallel):
    import glob
    import gunicorn.app.base

    class Unicorn(gunicorn.app.base.BaseApplication):

        def load_config(self):
            self.cfg.set('bind', f'{host}:{port}')
            workers = parallel
            if debug:
                self.cfg.set('accesslog', '-')
                self.cfg.set('reload', True)
                here = os.path.dirname(__file__)
                extras = []
                for name in ('static', 'templates'):
                    extras.extend(glob.glob(os.path.join(here, name, '*')))
                self.cfg.set('reload_extra_files', extras)
                workers = 1
            self.cfg.set('workers', workers)

        def load(self):
            return app

    Unicorn().run()

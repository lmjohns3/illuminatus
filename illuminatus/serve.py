import arrow
import collections
import contextlib
import flask
# import flask_socketio
import flask_sqlalchemy
import json
import os
import shutil
import tempfile

from . import db
from . import importexport

from .assets import Asset
from .query import assets as matching_assets

app = flask.Flask('illuminatus')
sql = flask_sqlalchemy.SQLAlchemy()


def _get_asset(slug):
    return sql.session.query(Asset).filter(Asset.slug.startswith(slug)).one()


# socketio = flask_socketio.SocketIO(app)
# @socketio.on('foo event')
# def handle_foo_event(json):
#     return 'a'


@app.route('/rest/formats/')
def formats():
    return flask.jsonify(app.config['formats'])


@app.route('/rest/query/<path:query>')
def assets(query):
    get = flask.request.args.get
    assets = matching_assets(sql.session,
                             query.split('/'),
                             order=get('order', 'stamp'),
                             limit=int(get('limit', 99999)),
                             offset=int(get('offset', 0))).all()
    return flask.jsonify([a.to_dict(slug_size=app.config['slug-size']) for a in assets])


@app.route('/rest/export/<path:query>', methods=['POST'])
def export(query):
    get = flask.request.form.get
    db = app.config['db']
    dirname = tempfile.mkdtemp()

    importexport.Exporter(
        matching_assets(sql.session, query.split('/')),
        json.loads(get('formats')),
    ).run(
        output=os.path.join(dirname, f'{get("name").zip}'),
        hide_tags=get('hide_tags', '').split(),
        hide_metadata_tags=get('hide_metadata_tags', '') == '1',
        hide_datetime_tags=get('hide_datetime_tags', '') == '1',
        hide_omnipresent_tags=get('hide_omnipresent_tags', '1') == '1',
    )

    @flask.after_this_request
    def cleanup(response):
        shutil.rmtree(dirname)
        return response

    return flask.send_file(output, as_attachment=True)


@app.route('/rest/asset/<string:slug>/', methods=['GET'])
def get_asset(slug):
    return flask.jsonify(_get_asset(slug).to_dict(slug_size=app.config['slug-size']))


@app.route('/rest/asset/<string:slug>/similar/', methods=['GET'])
def get_similar_assets(slug):
    similar = _get_asset(slug).similar(
        sql.session,
        hash=flask.request.args.get('hash', 'DIFF_6'),
        max_diff=float(flask.request.args.get('max-diff', 0.1)))
    return flask.jsonify([a.to_dict(slug_size=app.config['slug-size']) for a in similar])


@app.route('/rest/asset/<string:slug>/', methods=['PUT'])
def update_asset(slug):
    get = flask.request.form.get
    asset = _get_asset(slug)
    for tag in get('add_tags', '').split():
        asset.add_tag(tag)
    for tag in get('remove_tags', '').split():
        asset.remove_tag(tag)
    stamp = get('stamp', '')
    if stamp:
        asset.update_stamp(stamp)
    asset.save()
    return flask.jsonify(asset.to_dict(slug_size=app.config['slug-size']))


@app.route('/rest/asset/<string:slug>/', methods=['DELETE'])
def delete_asset(slug):
    _get_asset(slug).delete(hide_original=app.config['hide-originals'])
    return flask.jsonify('ok')


FILTER_ARGS = dict(
    autocontrast='percent',
    brightness='percent',
    contrast='percent',
    crop='x1 x2 y1 y2',
    hflip='',
    hue='degrees',
    rotate='degrees',
    saturation='percent',
    trim='',
    vflip='',
)


@app.route('/rest/asset/<string:slug>/filters/<string:filter>/', methods=['POST'])
def add_filter(slug, filter):
    kwargs = dict(filter=filter)
    for arg in FILTER_ARGS[filter].split():
        kwargs[arg] = float(flask.request.form[arg])
    asset = _get_asset(slug)
    asset.add_filter(kwargs)
    medium = asset.medium.name.lower()
    for path, kwargs in app.config['formats'][medium].items():
        kw = dict(slug=asset.slug,
                  dirname=app.config['thumbnails'],
                  overwrite=True)
        kw.update(kwargs)
        queue = 'video' if medium == 'video' and path == 'medium' else 'celery'
        tasks.export.apply_async(kwargs=kw, queue=queue)
    return flask.jsonify(asset.to_dict(slug_size=app.config['slug-size']))


@app.route('/rest/asset/<string:slug>/filters/<string:filter>/<int:index>/',
           methods=['DELETE'])
def delete_filter(slug, filter, index):
    asset = _get_asset(slug)
    asset.remove_filter(filter, index)
    medium = asset.medium.name.lower()
    for path, kwargs in app.config['formats'][medium].items():
        kw = dict(slug=asset.slug,
                  dirname=app.config['thumbnails'],
                  overwrite=True)
        kw.update(kwargs)
        queue = 'video' if medium == 'video' and path == 'medium' else 'celery'
        tasks.export.apply_async(kwargs=kw, queue=queue)
    return flask.jsonify(asset.to_dict(slug_size=app.config['slug-size']))


@app.route('/asset/<path:path>')
def thumb(path):
    return flask.send_file(os.path.join(app.config['thumbnails'], path))


@app.route('/manifest.json')
def manifest():
    return flask.jsonify(dict(
        short_name='Awww',
        name='Illuminatus',
        icons=[dict(src='icon.png', sizes='192x192', type='image/png')],
        start_url='/',
        display='standalone',
        orientation='portrait',
    ))


@app.route('/')
@app.route('/edit/<string:slug>/')
@app.route('/label/<string:slug>/')
@app.route('/cluster/<string:slug>/')
@app.route('/view/<path:query>')
def index(*args, **kwargs):
    return flask.render_template('index.html')

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
from . import metadata
from . import tools

app = flask.Flask('illuminatus')
sql = flask_sqlalchemy.SQLAlchemy()


def _get_asset(hash):
    return sql.session.query(db.Asset).filter(db.Asset.path_hash.startswith(hash)).one()


# socketio = flask_socketio.SocketIO(app)
# @socketio.on('foo event')
# def handle_foo_event(json):
#     return 'a'


@app.route('/rest/formats/')
def formats():
    return flask.jsonify(app.config['thumbnails']['formats'])


@app.route('/rest/query/<path:query>')
def assets(query):
    req = flask.request
    assets = (db.Asset.matching(sql.session, ' '.join(filter(None, query.split('/'))))
              .order_by(db.parse_order(req.args.get('order', 'stamp')))
              .limit(int(req.args.get('limit', 99999)))
              .offset(int(req.args.get('offset', 0)))
              .all())
    return flask.jsonify([a.to_dict() for a in assets])


@app.route('/rest/export/<path:query>', methods=['POST'])
def export(query):
    req = flask.request
    db = app.config['db']
    dirname = tempfile.mkdtemp()

    importexport.Exporter(
        db.Tag.query(sql.session).all(),
        db.Asset.matching(sql.session, ' '.join(filter(None, query.split('/')))),
        json.loads(req.form[formats]),
    ).run(
        output=os.path.join(dirname, req.form['name'] + '.zip'),
        hide_tags=req.form.get('hide_tags', '').split(),
        hide_metadata_tags=req.form.get('hide_metadata_tags', '') == '1',
        hide_datetime_tags=req.form.get('hide_datetime_tags', '') == '1',
        hide_omnipresent_tags=req.form.get('hide_omnipresent_tags', '1') == '1',
    )

    @flask.after_this_request
    def cleanup(response):
        shutil.rmtree(dirname)
        return response

    return flask.send_file(output, as_attachment=True)


@app.route('/rest/asset/<string:hash>/', methods=['GET'])
def get_asset(hash):
    return flask.jsonify(_get_asset(hash).to_dict())


@app.route('/rest/asset/<string:hash>/similar/', methods=['GET'])
def get_similar_assets(hash):
    asset = asset = _get_asset(hash)
    distance = int(flask.request.args.get('distance', 2))
    similar = asset.select_similar(sql.session, distance)
    return flask.jsonify([a.to_dict() for a in similar])


@app.route('/rest/asset/<string:hash>/', methods=['PUT'])
def update_asset(hash):
    req = flask.request
    stamp = req.form.get('stamp', '')
    add_tags = req.form.get('add_tags', '').split()
    remove_tags = req.form.get('remove_tags', '').split()
    asset = _get_asset(hash)
    for tag in add_tags:
        asset.add_tag(tag)
    for tag in remove_tags:
        asset.remove_tag(tag)
    if stamp:
        asset.update_stamp(stamp)
    asset.save()
    return flask.jsonify(asset.to_dict())


@app.route('/rest/asset/<string:hash>/', methods=['DELETE'])
def delete_asset(hash):
    _get_asset(hash).delete(hide_original=app.config['hide-originals'])
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

@app.route('/rest/asset/<string:hash>/filters/<string:filter>/', methods=['POST'])
def add_filter(hash, filter):
    req = flask.request
    kwargs = dict(filter=filter)
    for arg in FILTER_ARGS[filter].split():
        kwargs[arg] = float(req.form[arg])
    asset = _get_asset(hash)
    asset.add_filter(kwargs)
    asset.save()
    root = app.config['db'].root
    for s in app.config['sizes']:
        asset.export(s, root, force=True)
    return flask.jsonify(asset.to_dict())


@app.route('/rest/asset/<string:hash>/filters/<string:filter>/<int:index>/', methods=['DELETE'])
def delete_filter(hash, filter, index):
    asset = _get_asset(hash)
    asset.remove_filter(filter, index)
    asset.save()
    root = app.config['db'].root
    for s in app.config['sizes']:
        asset.export(s, root, force=True)
    return flask.jsonify(asset.to_dict())


@app.route('/asset/<path:path>')
def thumb(path):
    return flask.send_file(os.path.join(app.config['thumbnails']['root'], path))


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
@app.route('/edit/<string:hash>/')
@app.route('/label/<string:hash>/')
@app.route('/cluster/<string:hash>/')
@app.route('/view/<string:hash>/')
@app.route('/browse/<path:query>')
def index(*args, **kwargs):
    return flask.render_template('index.html')

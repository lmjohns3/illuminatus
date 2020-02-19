import arrow
import collections
import contextlib
import flask
import flask_sqlalchemy
import os
import shutil
import tempfile

from . import db
from . import importexport
from . import tools

app = flask.Flask('illuminatus')
sql = flask_sqlalchemy.SQLAlchemy()


@app.route('/query/<string:query>/')
def query(query):
    req = flask.request
    order = req.args.get('order', 'random')
    assets = (db.Asset.matching(sql.session, query, order=order)
              .limit(int(req.args.get('limit', 0)))
              .offset(int(req.args.get('offset', 0))))
    return flask.jsonify(assets=[a.to_dict() for a in assets])


@app.route('/export/<string:query>/', methods=['POST'])
def export(query):
    req = flask.request
    formats = {'{}_format'.format(medium): Format.parse(req.form[medium])
               for medium in ('audio', 'photo', 'video')}

    db = app.config['db']
    dirname = tempfile.mkdtemp()
    importexport.Exporter(db.tags, db.select(query), **formats).run(
        output=os.path.join(dirname, req.form['name'] + '.zip'),
        hide_tags=req.form.get('hide_tags', '').split(),
        hide_metadata_tags=req.form.get('hide_metadata_tags') == '1',
        hide_datetime_tags=req.form.get('hide_datetime_tags') == '1',
        hide_omnipresent_tags=req.form.get('hide_omnipresent_tags') == '1',
    )

    @flask.after_this_request
    def cleanup(response):
        shutil.rmtree(dirname)
        return response

    return flask.send_file(output, as_attachment=True)


@app.route('/asset/<int:id>/', methods=['PUT'])
def update_asset(id):
    req = flask.request
    stamp = req.form.get('stamp', '')
    add_tags = req.form.get('add_tags', '').split()
    remove_tags = req.form.get('remove_tags', '').split()
    with get_asset(id) as asset:
        for tag in add_tags:
            asset.add_tag(tag)
        for tag in remove_tags:
            asset.remove_tag(tag)
        if stamp:
            asset.update_stamp(stamp)
        asset.save()
        return flask.jsonify(asset.to_dict())


@app.route('/asset/<int:id>/', methods=['DELETE'])
def delete_asset(id):
    with get_asset(id) as asset:
        asset.delete(hide_original=app.config['hide-originals'])
        return flask.jsonify('ok')


@app.route('/asset/<int:id>/filters/<string:filter>', methods=['POST'])
def add_filter(id, filter):
    req = flask.request
    kwargs = dict(filter=filter)
    for arg in tools.FILTER_ARGS[filter].split():
        kwargs[arg] = float(req.form[arg])
    with get_asset(id) as asset:
        asset.add_filter(kwargs)
        asset.save()
        root = app.config['db'].root
        for s in app.config['sizes']:
            asset.export(s, root, force=True)
        return flask.jsonify(asset.rec)


@app.route('/asset/<int:id>/filters/<string:filter>/<int:index>', methods=['DELETE'])
def delete_filter(id, filter, index):
    with get_asset(id) as asset:
        asset.remove_filter(filter, index)
        asset.save()
        root = app.config['db'].root
        for s in app.config['sizes']:
            asset.export(s, root, force=True)
        return flask.jsonify(asset.rec)


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


@app.route('/', defaults=dict(tags=''))
@app.route('/<path:tags>')
def index(tags):
    if not tags:
        return flask.redirect(arrow.get().format('/YYYY/'))
    tags = tuple(t.strip().lower() for t in tags.split('/') if t.strip())
    assets = db.Asset.matching(sql.session, ' and '.join(tags))
    active_tags = set()
    remaining_tags = collections.defaultdict(int)
    for asset in assets:
        for tag in asset.tags:
            if tag.name in tags:
                active_tags.add(tag)
            else:
                remaining_tags[tag] += 1
    for tag in active_tags:
        tag.url = '/'.join(t.name for t in active_tags if t.name != tag.name)
        print(tag, tag.url)
    order = db.parse_order(flask.request.args.get('s', 'stamp-'))
    return flask.render_template(
        'index.html',
        now=arrow.get(),
        active_tags=sorted(active_tags, key=lambda t: (t.group, t.name)),
        remaining_tags=sorted(remaining_tags, key=lambda t: (t.group, t.name)),
        assets=assets.order_by(order))

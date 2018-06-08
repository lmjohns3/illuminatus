import arrow
import contextlib
import parsimonious.grammar
import sqlalchemy

from . import media


@sqlalchemy.event.listens_for(sqlalchemy.engine.Engine, 'connect')
def set_sqlite_pragma(dbapi_connection, connection_record):
    cur = dbapi_connection.cursor()
    cur.execute('PRAGMA encoding = "UTF-8"')
    cur.execute('PRAGMA foreign_keys = ON')
    cur.execute('PRAGMA journal_mode = WAL')
    cur.execute('PRAGMA synchronous = NORMAL')
    cur.close()


def db_uri(path):
    return 'sqlite:///{}'.format(path)


def engine(path, echo=False):
    return sqlalchemy.create_engine(db_uri(path), echo=echo)


def init(path):
    media.Model.metadata.create_all(engine(path))


@contextlib.contextmanager
def session(path, echo=False, hide_original_on_delete=False):
    session = sqlalchemy.orm.scoping.scoped_session(
        sqlalchemy.orm.sessionmaker(bind=engine(path, echo)))

    @sqlalchemy.event.listens_for(session, 'before_flush')
    def handle_asset_bookkeeping(sess, ctx, instances):
        for asset in sess.new:
            if isinstance(asset, media.Asset):
                asset._init()
                asset._rebuild_tags(sess)
        for asset in sess.dirty:
            if isinstance(asset, media.Asset):
                asset._rebuild_tags(sess)
        for asset in sess.deleted:
            if isinstance(asset, media.Asset):
                asset._maybe_hide_original(hide_original_on_delete)

    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.remove()


class QueryParser(parsimonious.NodeVisitor):
    '''Media can be queried using a special query syntax; we parse it here.

    The query syntax permits the following atoms, each of which represents a
    set of media assets in the database:

    - after:S -- selects media with timestamps greater than or equal to S
    - before:S -- selects media with timestamps less than or equal to S
    - path:S -- selects media with S in their paths
    - fp:S -- selects media asset with fingerprint S
    - S -- selects media tagged with S

    The specified sets can be combined using any combination of:

    - x or y -- contains media in either set x or set y
    - x and y -- contains media in both sets x and y
    - not y -- contains media not in set y

    Any of the operators above can be combined multiple times, and parentheses
    can be used to group sets together. For example, a and b or c selects media
    matching both a and b, or c, while a and (b or c) matches both a and d,
    where d consists of things in b or c.
    '''

    grammar = parsimonious.Grammar('''\
    query      = ( union / group )+
    union      = intersect ( _ 'or' _ intersect )*
    intersect  = negation ( _ 'and' _  negation )*
    negation   = 'not'? _ set
    set        = stamp / path / medium / hash / tag / group
    stamp      = ~'(before|after):\S+'
    path       = ~'path:\S+'
    medium     = ~'medium:(photo|video|audio)'
    hash       = ~'hash:[a-z0-9]+'
    tag        = ~'[-\w]+(:[-\w]+)*'
    group      = '(' _ query _ ')'
    _          = ~'\s*'
    ''')

    def __init__(self, db):
        self.db = db

    def generic_visit(self, node, children):
        return children or node.text

    def visit_query(self, node, children):
        [[child]] = children
        return child

    def visit_group(self, node, children):
        _, _, child, _, _ = children
        return child

    def visit_union(self, node, children):
        acc, rest = children
        for part in rest:
            acc = sqlalchemy.or_(acc, part[-1])
        return acc

    def visit_intersect(self, node, children):
        acc, rest = children
        for part in rest:
            acc = sqlalchemy.and_(acc, part[-1])
        return acc

    def visit_negation(self, node, children):
        neg, _, [filter] = children
        return ~filter if neg == ['not'] else filter

    def visit_tag(self, node, children):
        return media.Asset.tags.any(media.Tag.name == node.text)

    def visit_stamp(self, node, children):
        comp, value = node.text.split(':', 1)
        value = arrow.get(value, ['YYYY', 'YYYY-MM', 'YYYY-MM-DD']).datetime
        column = media.Asset.stamp
        return column < value if comp == 'before' else column > value

    def visit_path(self, node, visited_children):
        return media.Asset.path.ilike('%{}%'.format(node.text.split(':', 1)[1]))

    def visit_hash(self, node, visited_children):
        return media.Asset.hashes.any(
            media.Hash.nibbles.ilike('%{}%'.format(node.text.split(':', 1)[1])))

    def visit_medium(self, node, visited_children):
        return media.Asset.medium == node.text.split(':', 1)[1].capitalize()


def matching_assets(db, query, order=None):
    '''Find one or more media assets by parsing a query.

    Parameters
    ----------
    db : SQLAlchemy
        Database session.
    query : str
        Get transactions from the database matching these query clauses.
    order : str, optional
        A string giving the ordering for the query results, if any. If given,
        the string should name a field on the :class:`media.Asset`. If the
        string ends with '-' the ordering will be descending (defaults to
        ascending). Overall default is not to order the query results.

    Returns
    -------
    A list of :class:`media.Asset`s matching the query.
    '''
    rs = db.query(media.Asset)
    if query.strip():
        rs = rs.filter(QueryParser(db).parse(query))
    if order:
        descending = False
        if order.endswith('-'):
            descending = True
            order = order[:-1]
        how = getattr(media.Asset, order)
        rs = rs.order_by(how.desc() if descending else how)
    return rs

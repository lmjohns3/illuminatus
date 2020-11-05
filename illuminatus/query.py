import arrow
import itertools
import parsimonious.grammar
import sqlalchemy

from .assets import Asset, asset_tags
from .hashes import Hash
from .tags import Tag


def parse_order(order):
    '''Parse an ordering string into a SQL alchemy ordering spec.'''
    if order.lower().startswith('rand'):
        return sqlalchemy.func.random()
    descending = False
    if order.endswith('-'):
        descending = True
        order = order[:-1]
    how = getattr(Asset, order)
    return how.desc() if descending else how


class QueryParser(parsimonious.NodeVisitor):
    '''Media can be queried using a special query syntax; we parse it here.

    See docstring about query syntax in cli.py.
    '''

    grammar = parsimonious.Grammar(r'''
    query    = union ( __ ( not __ )? union )*
    union    = set ( __ or __ set )*
    set      = !not !or ( group / stamp / path / slug / hash / medium / tag )
    group    = '(' _ query _ ')'
    stamp    = ~r'(before|during|after):[-\d]+'
    path     = ~r'path:\S+'
    slug     = ~r'slug:[-\w]+'
    hash     = ~r'hash:[-=\w]+'
    medium   = ~'(photo|video|audio)'
    tag      = ~r'[-\w]+'
    not      = 'not'
    or       = 'or'
    _        = ~r'\s*'
    __       = ~r'\s+'
    ''')

    def __init__(self, sess):
        super().__init__()
        self.sess = sess

    def visit_query(self, node, children):
        select, rest = children
        for _, neg, other in rest:
            if neg:
                select = sqlalchemy.sql.except_(select, other)
            else:
                select = sqlalchemy.sql.intersect(select, other)
        return select

    def visit_union(self, node, children):
        select, rest = children
        for _, _, _, other in rest:
            select = sqlalchemy.sql.union(select, other)
        return select

    def visit_set(self, node, children):
        _, _, [child] = children
        return child

    def visit_group(self, node, children):
        _, _, child, _, _ = children
        return child

    def visit_stamp(self, node, children):
        comp, value = node.text.split(':', 1)
        value = arrow.get(value, ['YYYY', 'YYYY-MM', 'YYYY-MM-DD']).datetime
        return self.sess.query(Asset.id).filter(
            Asset.stamp < value if comp == 'before' else
            Asset.stamp > value if comp == 'after' else
            Asset.stamp.startswith(value))

    def visit_path(self, node, children):
        return self.sess.query(Asset.id).filter(Asset.path.contains(node.text[5:]))

    def visit_slug(self, node, children):
        return self.sess.query(Asset.id).filter(Asset.slug.startswith(node.text[5:]))

    def visit_medium(self, node, children):
        return self.sess.query(Asset.id).filter(Asset.medium == node.text.lower())

    def visit_tag(self, node, children):
        return sqlalchemy.sql.select([asset_tags.c.asset_id]).select_from(
            asset_tags.join(Tag, asset_tags.c.tag_id == Tag.id)
        ).where(Tag.name == node.text)

    def visit_hash(self, node, children):
        nibbles = node.text[5:]
        condition = Hash.nibbles.startswith(nibbles)
        if '=' in nibbles:
            method, nibbles = nibbles.split('=', 1)
            condition = Hash.nibbles.startswith(nibbles) & (Hash.method == method)
        return self.sess.query(Hash.asset_id).filter(condition)

    def generic_visit(self, node, children):
        return children or node.text


def assets(sess, *query, order=None, limit=None, offset=None):
    '''Find media assets matching a text query.

    Parameters
    ----------
    sess : SQLAlchemy
        Database session.
    query : str
        Get assets from the database matching these query clauses.
    order : str
        Order assets by this field.
    limit : int
        Limit the number of returned assets.
    offset : int
        Start at this position in the asset list.

    Returns
    -------
      A result set of :class:`Asset`s matching the query.
    '''
    query = ' '.join(itertools.chain.from_iterable(query)).strip()
    q = sess.query(Asset)
    if query:
        q = q.filter(Asset.id.in_(QueryParser(sess).parse(query)))
    if order:
        q = q.order_by(parse_order(order))
    if limit:
        q = q.limit(limit)
    if offset:
        q = q.offset(offset)
    return q

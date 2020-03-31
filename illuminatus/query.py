import arrow
import itertools
import parsimonious.grammar
import sqlalchemy

from .assets import Asset
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
    query    = union ( __ union )*
    union    = negation ( __ or __ negation )*
    negation = ( not __ )? set
    set      = !not !or ( group / stamp / path / slug / hash / medium / text / tag )
    group    = '(' _ query _ ')'
    stamp    = ~r'(before|during|after):[-\d]+'
    path     = ~r'path:\S+'
    slug     = ~r'slug:[-\w]+'
    hash     = ~r'hash:[-\w]+'
    medium   = ~'(photo|video|audio)'
    text     = ~'"[^"]+"'
    tag      = ~r'[-\w]+'
    not      = 'not'
    or       = 'or'
    _        = ~r'\s*'
    __       = ~r'\s+'
    ''')

    def visit_query(self, node, children):
        intersection, rest = children
        for elem in rest:
            intersection &= elem[-1]
        return intersection

    def visit_union(self, node, children):
        union, rest = children
        for elem in rest:
            union |= elem[-1]
        return union

    def visit_negation(self, node, children):
        neg, which = children
        return ~which if neg else which

    def visit_set(self, node, children):
        _, _, [child] = children
        return child

    def visit_group(self, node, children):
        _, _, child, _, _ = children
        return child

    def visit_stamp(self, node, children):
        comp, value = node.text.split(':', 1)
        value = arrow.get(value, ['YYYY', 'YYYY-MM', 'YYYY-MM-DD']).datetime
        column = Asset.stamp
        return (column < value if comp == 'before' else
                column > value if comp == 'after' else
                column.startswith(value))

    def visit_path(self, node, children):
        return Asset.path.contains(node.text[5:])

    def visit_slug(self, node, children):
        return Asset.slug.startswith(node.text[5:])

    def visit_hash(self, node, children):
        return Asset.hashes.any(Hash.nibbles.contains((node.text[5:])))

    def visit_medium(self, node, children):
        return Asset.medium == Asset.Medium[node.text.capitalize()]

    def visit_text(self, node, children):
        s = node.text.strip('"')
        return Asset.description.contains(s) | Asset.tags.any(Tag.name == s)

    def visit_tag(self, node, children):
        s = node.text
        return Asset.description.contains(s) | Asset.tags.any(Tag.name == s)

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
        q = q.filter(QueryParser().parse(query))
    if order:
        q = q.order_by(parse_order(order))
    if limit:
        q = q.limit(limit)
    if offset:
        q = q.offset(offset)
    return q

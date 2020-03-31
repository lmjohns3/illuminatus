import click
import enum
import numpy as np
import PIL.Image
import sqlalchemy

from . import db


class Hash(db.Model):
    __tablename__ = 'hashes'

    @enum.unique
    class Flavor(str, enum.Enum):
        '''Enumeration of different supported hash types.'''
        DIFF_4 = 'diff-4'
        DIFF_6 = 'diff-6'
        DIFF_8 = 'diff-8'
        DIFF_10 = 'diff-10'

        HSL_HIST_4 = 'hsl-hist-4'
        HSL_HIST_8 = 'hsl-hist-8'
        HSL_HIST_16 = 'hsl-hist-16'

        RGB_HIST_4 = 'rgb-hist-4'
        RGB_HIST_8 = 'rgb-hist-8'
        RGB_HIST_16 = 'rgb-hist-16'

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False)
    nibbles = db.Column(db.String, index=True, nullable=False)
    flavor = db.Column(db.Enum(Flavor), index=True, nullable=False)
    time = db.Column(db.Float)

    asset = sqlalchemy.orm.relationship(
        'Asset', backref=sqlalchemy.orm.backref('hashes', collection_class=set),
        lazy='selectin', collection_class=set)

    def __lt__(self, other):
        return self.nibbles < other.nibbles

    def __repr__(self):
        return '#'.join((click.style(self.flavor.value, fg='blue'),
                         click.style(self.nibbles, fg='cyan', bold=True)))

    @classmethod
    def compute_photo_diff(cls, path, size=4):
        '''Compute a similarity hash for an image.

        Parameters
        ----------
        path : str
            Path to an image file on disk.
        size : int, optional
            Number of pixels, `s`, per side for the image. The hash will have
            `s * s` bits. Must correspond to one of the available DIFF_N hash
            flavors.

        Returns
        -------
        A Hash instance representing the diff hash.
        '''
        gray = PIL.Image.open(path).convert('L')
        pixels = np.asarray(gray.resize((size + 1, size), PIL.Image.ANTIALIAS))
        return cls(nibbles=_bits_to_nibbles(pixels[:, 1:] > pixels[:, :-1]),
                   flavor=Hash.Flavor[f'DIFF_{size}'])

    @classmethod
    def compute_photo_histogram(cls, path, planes='RGB', size=4):
        hist = np.asarray(PIL.Image.open(path).convert(planes).histogram())
        chunks = np.asarray([c.sum() for c in np.split(hist, 3 * size)])
        # This makes 50% of bits into ones, is that a good idea?
        return cls(nibbles=_bits_to_nibbles(chunks > np.percentile(chunks, 50)),
                   flavor=Hash.Flavor[f'{planes}_HIST_{size}'])

    @classmethod
    def compute_audio_diff(cls, path, size=8):
        raise NotImplementedError

    @classmethod
    def compute_video_diff(cls, path, time, size=8):
        return cls(nibbles='', flavor=Hash.Flavor[f'DIFF_{size}'], time=time)

    def neighbors(self, sess, max_diff):
        '''Get all neighboring hashes from the database.

        Parameters
        ----------
        sess : SQLAlchemy
            Database session.
        max_diff : float, optional
            Select all existing hashes within this fraction of changed bits.

        Returns
        -------
        A query object over neighboring hashes from our hash.
        '''
        return (
            sess.query(Hash)
            .filter(Hash.flavor == self.flavor)
            .filter(Hash.nibbles.in_(_neighbors(self.nibbles, max_diff)))
            .yield_per(1000)
        )

    def to_dict(self):
        return dict(nibbles=self.nibbles, flavor=self.flavor, time=self.time)


def _bits_to_nibbles(bits):
    '''Convert a boolean ndarray of bits to a hex string.'''
    flat = bits.ravel()
    if flat.size % 4:
        raise ValueError(f'Cannot convert {flat.size} bits to hex nibbles')
    return ('{:0%dx}' % (flat.size // 4, )).format(
        int(''.join(flat.astype(int).astype(str)), 2))


def _bit_diff_rate(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count('1') / len(a) / 4


# a map from each hex digit to the hex digits that differ in 1 bit.
_HEX_NEIGHBORS = {'0': '1248', '1': '0359', '2': '306a', '3': '217b',
                  '4': '560c', '5': '471d', '6': '742e', '7': '653f',
                  '8': '9ac0', '9': '8bd1', 'a': 'b8e2', 'b': 'a9f3',
                  'c': 'de84', 'd': 'cf95', 'e': 'fca6', 'f': 'edb7'}


def _neighbors(start, max_diff=0.01):
    '''Pull all neighboring hashes within a similarity ball from the start.

    Parameters
    ----------
    start : str
        Hexadecimal string representing a starting hash value.
    max_diff : float, optional
        Identify all hashes within this fraction of changed bits from the start.

    Yields
    -------
    The unique hashes that are within the given fraction of changed bits from
    the start.
    '''
    if not start:
        return
    visited, frontier = {start}, {start}
    while frontier:
        yield from frontier
        next_frontier = set()
        for nibbles in frontier:
            for i, c in enumerate(nibbles):
                for d in _HEX_NEIGHBORS[c]:
                    n = f'{nibbles[:i]}{d}{nibbles[i+1:]}'
                    if n not in visited and _bit_diff_rate(start, n) <= max_diff:
                        next_frontier.add(n)
                        visited.add(n)
        frontier = next_frontier

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
        DIFF_4 = 'DIFF_4'
        DIFF_6 = 'DIFF_6'
        DIFF_8 = 'DIFF_8'

        HSL_HIST_4 = 'HSL_HIST_4'
        HSL_HIST_8 = 'HSL_HIST_8'
        HSL_HIST_16 = 'HSL_HIST_16'

        RGB_HIST_4 = 'RGB_HIST_4'
        RGB_HIST_8 = 'RGB_HIST_8'
        RGB_HIST_16 = 'RGB_HIST_16'

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
        return f'<Hash {self.flavor}:{self.nibbles}@{self.time}>'

    @property
    def click(self):
        return ':'.join((click.style(self.flavor.name, fg='white'),
                         click.style(self.nibbles, fg='white', bold=True)))

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

    def neighbors(self, sess, min_similarity=0.99):
        '''Get all neighboring hashes from the database.

        Parameters
        ----------
        sess : SQLAlchemy
            Database session.
        min_similarity : float, optional
            Select all existing hashes within this fraction of changed bits.

        Returns
        -------
        A query object over neighboring hashes from our hash.
        '''
        return (
            sess.query(Hash)
            .filter(Hash.flavor == self.flavor)
            .filter(Hash.nibbles.in_(_neighbors(self.nibbles, min_similarity)))
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


# a map from each hex digit to the hex digits that differ in 1 bit.
_HEX_NEIGHBORS = {'0': '1248', '1': '0359', '2': '306a', '3': '217b',
                  '4': '560c', '5': '471d', '6': '742e', '7': '653f',
                  '8': '9ac0', '9': '8bd1', 'a': 'b8e2', 'b': 'a9f3',
                  'c': 'de84', 'd': 'cf95', 'e': 'fca6', 'f': 'edb7'}


def _neighbors(start, min_similarity=0.99):
    '''Pull all neighboring hashes within a similarity ball from the start.

    Parameters
    ----------
    start : str
        Hexadecimal string representing a starting hash value.
    min_similarity : float, optional
        Identify all hashes within this fraction of changed bits from the start.

    Yields
    -------
    The unique hashes that are within the given fraction of changed bits from
    the start.
    '''
    visited, frontier = set(), {start}
    yield start
    for _ in range(3):
        visited |= frontier
        frontier = {f'{nibbles[:i]}{d}{nibbles[i+1:]}'
                    for nibbles in frontier
                    for i, c in enumerate(nibbles)
                    for d in _HEX_NEIGHBORS[c]} - visited
        yield from frontier

import click
import numpy as np
import PIL.Image
import sqlalchemy

from . import db


def _bits_to_nibbles(bits):
    '''Convert a boolean ndarray of bits to a hex string.'''
    flat = bits.ravel()
    if flat.size % 4:
        raise ValueError(f'Cannot convert {flat.size} bits to hex nibbles')
    num = sum(1 << i for i, c in enumerate(reversed(flat)) if c)
    return hex(num)[2:].zfill(flat.size // 4)


def _bit_diff_rate(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count('1') / len(a) / 4


# http://www.hackerfactor.com/blog/index.php?/archives/529-Kind-of-Like-That.html
def _dhash(img, size):
    if isinstance(img, np.ndarray):
        img = PIL.Image.fromarray(img)
    arr = np.array(img.resize((size + 1, size)))
    return _bits_to_nibbles(arr[:, 1:] > arr[:, :-1])


class Hash(db.Model):
    __tablename__ = 'hashes'

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.ForeignKey('assets.id', ondelete='CASCADE'), nullable=False)
    nibbles = db.Column(db.String, index=True, nullable=False)
    method = db.Column(db.String, index=True, nullable=False)
    time = db.Column(db.Float)

    asset = sqlalchemy.orm.relationship(
        'Asset', backref=sqlalchemy.orm.backref('hashes', lazy=False, collection_class=set),
        lazy='selectin', collection_class=set)

    def __repr__(self):
        return '#'.join((click.style(self.method, fg='blue'),
                         click.style(self.nibbles, fg='cyan', bold=True)))

    @classmethod
    def compute_photo_dhash(cls, img, size):
        '''Compute a "difference hash" for an image.

        Parameters
        ----------
        img : PIL.Image
            An image.
        size : int
            Number of pixels per side of the image; hash will have n^2 bits.

        Returns
        -------
        A Hash instance representing the diff hash.
        '''
        w, h = img.size
        c, x, y = min(w, h) // 2, w // 2, h // 2
        return cls(method=f'dhash-{size}',
                   nibbles=_dhash(img.crop((x - c, y - c, x + c, y + c)), size))

    @classmethod
    def compute_photo_histogram(cls, img, planes, size):
        '''Compute a hash based on a RGB or HSL histogram.

        Bits in the hash are computed based on whether they are above or below
        the median histogram value.

        Parameters
        ----------
        img : PIL.Image
            An image.
        planes : str
            Color planes that are being used for the histogram.
        size : int
            Number of bits per plane in the histogram. The total number of bits
            in the hash is 3x this value.

        Returns
        -------
        A Hash instance representing the histogram.
        '''
        hist = np.asarray(img.convert('RGB').histogram())
        chunks = np.asarray([c.sum() for c in np.split(hist, 3 * size)])
        # Bits indicate whether each chunk is above or below the mean.
        return cls(nibbles=_bits_to_nibbles(chunks > np.mean(chunks)),
                   method=f'{planes}-{size}'.lower())

    @classmethod
    def compute_audio_dhash(cls, img, time, size):
        '''Compute a dhash for an audio spectrogram at a specific time.

        Parameters
        ----------
        img : np.ndarray
            A numpy array containing a log-mel power spectrum.
        time : int
            Number of seconds along the time axis where for computing the hash.
        size : int
            Size of each side of the dhash image patch. The total number of
            bits in the hash will be n^2.
        '''
        return cls(nibbles=_dhash(img[time:time+img.shape[1]], size),
                   method=f'dhash-{size}', time=time)

    @classmethod
    def compute_video_dhash(cls, path, time, size):
        return cls(nibbles=_dhash(path, size), method=f'dhash-{size}', time=time)

    def neighbors(self, sess, max_distance=1):
        '''Get all neighboring hashes from the database.

        Parameters
        ----------
        sess : SQLAlchemy
            Database session.
        max_distance : int, optional
            Select all existing hashes within this many changed bits.

        Returns
        -------
        A query object over neighboring hashes from our hash.
        '''
        return (
            sess.query(Hash)
            .filter(Hash.method == self.method)
            .filter(Hash.nibbles.in_(_neighbors(self.nibbles, max_distance)))
            .yield_per(1000)
        )

    def to_dict(self):
        return dict(nibbles=self.nibbles, method=self.method, time=self.time)


# a map from each hex digit to the hex digits that differ in 1 bit.
_HEX_NEIGHBORS = {'0': '1248', '1': '0359', '2': '306a', '3': '217b',
                  '4': '560c', '5': '471d', '6': '742e', '7': '653f',
                  '8': '9ac0', '9': '8bd1', 'a': 'b8e2', 'b': 'a9f3',
                  'c': 'de84', 'd': 'cf95', 'e': 'fca6', 'f': 'edb7'}


def _neighbors(start, max_distance=1):
    '''Pull all neighboring hashes within a similarity ball from the start.

    Parameters
    ----------
    start : str
        Hexadecimal string representing a starting hash value.
    max_distance : int, optional
        Identify all hashes within this many changed bits from the start.

    Yields
    -------
    The unique hashes that are within the given distance from the start.
    '''
    if not start:
        return
    visited, frontier = {start}, {start}
    for _ in range(max_distance):
        yield from frontier
        next_frontier = set()
        for nibbles in frontier:
            for i, c in enumerate(nibbles):
                for d in _HEX_NEIGHBORS[c]:
                    n = f'{nibbles[:i]}{d}{nibbles[i+1:]}'
                    if n not in visited:
                        next_frontier.add(n)
                        visited.add(n)
        frontier = next_frontier

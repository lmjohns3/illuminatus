'''Code for transforming RGB <--> HSL colorspaces.

Based on explanations at http://en.wikipedia.org/wiki/HSL_and_HSV
'''

import climate
import numpy as np
import PIL.Image
import PIL.ImageOps

logging = climate.get_logger(__name__)


def f2i(x):
    '''Scale a floating-point array x with values in [0, 1) to uint8.'''
    return (255 * x).astype(np.uint8)


def rgb_to_y(R, G, B):
    '''Return a "perceptual monochrome" ("luma") version of an image.'''
    return 0.30 * R + 0.59 * G + 0.11 * B


def rgb_to_hsl(R, G, B):
    '''Convert arrays of R, G, B values to arrays of H, S, L values.

    The R, G, B values are assumed to be arrays of uint8.

    The resulting H, S, L values are floating point arrays. The S and L arrays
    vary from 0 to 1, while the H array varies from 0 to 360.

    Adapted from http://stackoverflow.com/questions/4890373/detecting-thresholds-in-hsv-color-space-from-rgb-using-python-pil/4890878#4890878
    '''
    m = np.min([R, G, B], axis=0)
    M = np.max([R, G, B], axis=0)

    L = (M + m) / 255. / 2
    logging.debug('L: %.3f-%.3f', L.min(), L.max())

    C = (M - m).astype(float) / 255.
    logging.debug('C: %.3f - %.3f', C.min(), C.max())
    Cmask = M != m

    H = np.zeros(R.shape, float)
    mask = (M == R) & Cmask
    H[mask] = np.mod(60. * (G - B)[mask] / C[mask] / 255., 360.)
    mask = (M == G) & Cmask
    H[mask] = 60. * (B - R)[mask] / C[mask] / 255. + 120.
    mask = (M == B) & Cmask
    H[mask] = 60. * (R - G)[mask] / C[mask] / 255. + 240.
    logging.debug('H: %.3f-%.3f', H.min(), H.max())

    S = np.zeros(R.shape, float)
    mask = (0 < L) & (L < 1) & Cmask
    S[mask] = C[mask] / (1 - abs(2 * L[mask] - 1))
    logging.debug('S: %.3f-%.3f', S.min(), S.max())

    return H, S, L


def hsl_to_rgb(H, S, L):
    '''Convert arrays of H, S, L values to arrays of R, G, B values.

    The H, S, L values are assumed to be floating point arrays. The S and L
    arrays should vary from 0 to 1, while the H array should vary from 0 to 360.

    The R, G, B values are returned as arrays of uint8.
    '''
    C = S * (1 - abs(2 * L - 1))

    Hprime = H / 60.
    X = C * (1 - abs(np.mod(Hprime, 2) - 1))
    Z = np.zeros(H.shape, float)

    R = Z + 0
    G = Z + 0
    B = Z + 0

    mask = (0 <= Hprime) & (Hprime < 1)
    R[mask], G[mask], B[mask] = C[mask], X[mask], Z[mask]
    mask = (1 <= Hprime) & (Hprime < 2)
    R[mask], G[mask], B[mask] = X[mask], C[mask], Z[mask]
    mask = (2 <= Hprime) & (Hprime < 3)
    R[mask], G[mask], B[mask] = Z[mask], C[mask], X[mask]
    mask = (3 <= Hprime) & (Hprime < 4)
    R[mask], G[mask], B[mask] = Z[mask], X[mask], C[mask]
    mask = (4 <= Hprime) & (Hprime < 5)
    R[mask], G[mask], B[mask] = X[mask], Z[mask], C[mask]
    mask = (5 <= Hprime) & (Hprime < 6)
    R[mask], G[mask], B[mask] = C[mask], Z[mask], X[mask]

    m = L - 0.5 * C
    return f2i(R + m), f2i(G + m), f2i(B + m)

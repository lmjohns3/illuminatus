import os
import setuptools

# take description from README.md
here = os.path.dirname(os.path.abspath(__file__))
readme = ''
try:
    readme = file(os.path.join(here, 'README.md')).read()
except (OSError, IOError):
    pass

setuptools.setup(
    name='lmj.photos',
    version='0.0.1',
    namespace_packages=['lmj'],
    packages=setuptools.find_packages(),
    requires=['PIL', 'lmj.cli', 'cv2', 'bottle'],
    scripts=['scripts/lmj-photos'],
    data_files=[('share/lmj-photos/web', [
        'web/photos.js',
        'web/photos.css',
        'web/main.html',
        'web/index.html',
        'web/photos.html',
        ]),
    ],
    author='Leif Johnson',
    author_email='leif@leifjohnson.net',
    description='A local, web-based tool for managing photos',
    long_description=readme,
    license='MIT',
    keywords='photo image web',
    url='http://github.com/lmjohns3/py-photos/',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        ],
    )

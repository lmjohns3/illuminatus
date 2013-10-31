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
    name='lmj.media',
    version='0.0.1',
    namespace_packages=['lmj'],
    packages=setuptools.find_packages(),
    requires=['PIL', 'lmj.cli', 'cv2', 'bottle'],
    scripts=['scripts/lmj-media'],
    data_files=[('share/lmj-media/static', [
        'static/media.js',
        'static/media.css',
        'static/views/main.html',
        'static/views/index.html',
        'static/views/photos.html',
        ]),
    ],
    author='Leif Johnson',
    author_email='leif@leifjohnson.net',
    description='A browser tool for managing photos and videos',
    long_description=readme,
    license='MIT',
    keywords='photo image video web',
    url='http://github.com/lmjohns3/py-media/',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        ],
    )

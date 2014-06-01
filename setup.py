import os
import setuptools

setuptools.setup(
    name='lmj.media',
    version='0.0.1',
    namespace_packages=['lmj'],
    packages=setuptools.find_packages(),
    requires=['bottle', 'climate', 'pillow'],
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
    description='tools for managing photos and videos',
    long_description=open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'README.rst')).read(),
    license='MIT',
    keywords='photo image video media database web',
    url='http://github.com/lmjohns3/py-media/',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        ],
    )

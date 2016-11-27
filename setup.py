import os
import setuptools

readme = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'README.rst')

setuptools.setup(
    name='illuminatus',
    version='0.0.1',
    packages=setuptools.find_packages(),
    requires=['bottle', 'linnmon'],
    scripts=['scripts/illuminatus'],
    author='Leif Johnson',
    author_email='leif@lmjohns3.com',
    description='Tools for managing videos, photos, and audio recordings',
    long_description=open(readme).read(),
    license='MIT',
    keywords='photo image video media database web',
    url='http://github.com/lmjohns3/illuminatus/',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        ],
    )

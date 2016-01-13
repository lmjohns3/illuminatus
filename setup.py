import os
import setuptools

setuptools.setup(
    name='illuminatus',
    version='0.0.1',
    packages=setuptools.find_packages(),
    requires=['bottle', 'climate', 'pillow'],
    scripts=['scripts/illuminatus'],
    author='Leif Johnson',
    author_email='leif@lmjohns3.com',
    description='Tools for managing photos and videos',
    long_description=open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'README.rst')).read(),
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

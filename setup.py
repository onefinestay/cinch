import os
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
make_abs = lambda fn: os.path.join(here, fn)


def unpinned_requirments(filename):
    with open(filename, 'r') as handle:
        for dep in handle:
            package, _ = dep.split('==')
            yield package


requirements = unpinned_requirments(make_abs('requirements.txt'))


setup(
    name='cinch',
    packages=find_packages(exclude=['tests', 'tests.*']),
    version='0.1.0',
    author='onefinestay',
    author_email='engineering@onefinestay.com',
    url='https://github.com/onefinestay/cinch',
    install_requires=requirements,
    license='Apache License, Version 2.0',
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Topic :: Software Development",
        "Topic :: Utilities",
    ],
    description='CInch - Making CI a cinch',
    long_description=open(make_abs('README.rst')).read(),
    include_package_data=True,
    zip_safe=False,
)

'''
Created on Nov 12, 2021

@author: cesare
'''
from setuptools import find_packages, setup


setup(
    name="sshmarketplacelib",
    packages=find_packages(include=['sshmarketplacelib']),
    version='0.1.0',
    include_package_data=True,
    description='SSHOC MarketPlace Python library',
    author='Cesare Concordia',
    install_requires=['pandas', 'numpy', 'requests', 'PyYAML', 'bokeh'],
    setup_requires=['pytest-runner'],
    tests_require=['pytest==4.4.1'],
    test_suite='test',
)

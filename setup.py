#!/usr/bin/env python3

from setuptools import setup, find_packages

setup(
    name='netdev_exporter',
    author='Bruce Merry',
    author_email='bmerry@ska.ac.za',
    description='Prometheus exporter for assorted NIC performance counters',
    packages=['netdev_exporter'],
    setup_requires=['katversion'],
    python_requires='>=3.5',
    install_requires=[
        'aiohttp',
        'prometheus_client<0.4.0',
        'katsdpservices'
    ],
    entry_points={
        'console_scripts': ['netdev-exporter = netdev_exporter:main']
    },
    use_katversion=True
)

# -*- encoding: utf-8 -*-
from setuptools import setup, find_packages
import sys
import os

version = '0.1'

if __name__ == '__main__':
    setup(
        name='taskdav',
        version=version,
        description="Task management for CalDAV task list",
        classifiers=["Development Status :: 4 - Beta",
                     "Intended Audience :: Developers",
                     "License :: OSI Approved :: GNU General Public License (GPL)",
                     "Operating System :: OS Independent",
                     "Programming Language :: Python",
                     "Topic :: Office/Business :: Scheduling",
                     ],
        keywords='',
        author='David Fraser',
        author_email='davidf@sjsoft.com',
        url='http://github.org/davidfraser/taskdav',
        license='GPL',
        packages=find_packages(),
        include_package_data=True,
        zip_safe=False,
        install_requires=['caldav', 'aaargh'],
        )


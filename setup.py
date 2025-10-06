#!/usr/bin/env python3
"""
Setup script for MailQuery library
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="mailquery",
    version="0.1.0",
    author="Phil",
    description="A jQuery-like fluent interface for email filtering and storage",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/mailquery",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Communications :: Email",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=[
        # No external dependencies for core functionality
        # imaplib and sqlite3 are part of Python standard library
    ],
    extras_require={
        "gmail": [
            "google-auth>=2.0.0",
            "google-auth-oauthlib>=1.0.0", 
            "google-auth-httplib2>=0.1.0",
            "google-api-python-client>=2.0.0",
        ],
        "dev": [
            "pytest",
            "pytest-cov",
        ],
    },
    entry_points={
        "console_scripts": [
            # No console scripts for this library
        ],
    },
) 
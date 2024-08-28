from setuptools import setup, find_packages

# Load the README file as the long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    # Basic package information
    name='goldflipper',  # The name of your package
    version='0.1.0',  # Initial version number (follow semantic versioning)
    author='Yaroshevskiy, Iliya',  # Replace with your name
    author_email='your.email@example.com',  # Replace with your email
    description='A Python package for algorithmic trading using Alpaca.',
    long_description=long_description,  # Long description from README.md
    long_description_content_type="text/markdown",  # The format of the long description
    url='https://github.com/yourusername/goldflipper',  # URL to the project homepage
    license='Proprietary. Copyright Purpleaf LLC. All rights reserved.',  # License under which the package is distributed

    # Package structure
    packages=find_packages(),  # Automatically discover and include all packages and sub-packages

    # Include additional files specified in MANIFEST.in
    include_package_data=True,

    # Package data to include within the package itself
    package_data={
        'goldflipper': [
            'tools/PlayTemplate',  # Include PlayTemplate in the tools directory
            'plays/*.json',  # Include all JSON files in the plays directory
            'config/*.py',  # Include all Python files in the config directory
        ],
    },

    # Specify the Python version compatibility
    python_requires='>=3.6',

    # Dependencies required for your package
    install_requires=[
        'alpaca-py',  # Alpaca trading API v2
        'yfinance',  # Yahoo Finance API for market data
        'pandas',  # Data analysis and manipulation library
        # Add any other dependencies here
    ],

    # Entry points to create command-line tools or scripts
    entry_points={
        'console_scripts': [
            'goldflipper=goldflipper.run:main',  # Assumes `main` function is in `run.py`
        ],
    },

    # Additional metadata for package indexing and classification
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: Proprietary. Copyright Purpleaf LLC. All rights reserved.',
        'Operating System :: OS Independent',
        'Development Status :: 4 - Beta',  # Project is in the beta stage
        'Intended Audience :: Developers',
        'Intended Audience :: Financial and Insurance Industry',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Office/Business :: Financial :: Investment',
    ],

    # Keywords related to the project (useful for PyPI and search)
    keywords='algorithmic trading alpaca finance stocks investment',

    # Project URLs for additional resources
    project_urls={
        'Bug Reports': 'https://github.com/yourusername/goldflipper/issues',
        'Source': 'https://github.com/yourusername/goldflipper',
        'Documentation': 'https://github.com/yourusername/goldflipper/wiki',
    },
)

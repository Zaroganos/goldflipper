from setuptools import setup, find_packages

# Load the README file as the long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='goldflipper',
    version='0.1.2',
    author='Yaroshevskiy, Iliya',
    author_email='purpleafmanagement@gmail.com',
    description='A Python program for semi-autonomous options trading on Alpaca.',
    long_description=long_description,  # Long description from README.md
    long_description_content_type="text/markdown",  # The format of the long description
    url='https://github.com/Zaroganos/goldflipper',
    license='Proprietary; copyright Iliya Yaroshevskiy; all rights reserved.',  # License under which the package is distributed

    # Package structure
    packages=find_packages(),  # Automatically discover and include all packages and sub-packages

    # Include additional files specified in MANIFEST.in
    include_package_data=True,

    # Package data to include within the package itself
    package_data={
        'goldflipper': [
            'tools/PlayTemplate',  # Include Play Template in the tools directory
            'plays/*.json',  # Include all JSON files in the plays directory
            'config/*.py',  # Include all Python files in the config directory
        ],
    },

    # Python version compatibility
    python_requires='>=3.9',

    # Dependencies required
    install_requires=[
        'alpaca-py>=0.8.0', # Alpaca trading API v2
        'yfinance==0.2.37', # Yahoo Finance API for market data !! KEEP AT THIS VERSION !! latest version is not working (fix in progress)
        'pandas>=2.0.0',  # Data analysis and manipulation library
        'numpy>=1.24.0',  # Numerical computing library
        'matplotlib>=3.7.0',  # Data visualization library
        'seaborn>=0.12.0',  # Data visualization library
        'scipy>=1.10.0',  # Scientific computing library
        'ta>=0.10.0',  # Technical analysis library
        'textual>=0.38.1',  # TUI library
        'psutil>=5.9.0',  # System monitoring library
        'nest-asyncio>=1.5.0', # Asynchronous library
        'pywin32',
        'tkinterdnd2>=0.3.0',  # For drag and drop support in the setup dialog
    ],

    # Entry points to create command-line tools or scripts
    entry_points={
        'console_scripts': [
            'goldflipper=goldflipper.run:main',  # Assumes `main` function is in `run.py`
        ],
    },

    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: Proprietary. Copyright Iliya Yaroshevskiy. All rights reserved.',
        'Operating System :: OS Independent',
        'Development Status :: 4 - Beta',
        'Intended Audience :: Internal Use Only',
        'Intended Audience :: Retail and Institutional Options Traders',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Office/Business :: Financial :: Investment',
    ],

    # Keywords related to the project (useful for PyPI and search)
    keywords='algorithmic trading alpaca finance stocks investment',

    # Project URLs for additional resources
    project_urls={
        'Bug Reports': 'https://github.com/Zaroganos/goldflipper/issues',
        'Source': 'https://github.com/Zaroganos/goldflipper',
        'Documentation': 'https://github.com/Zaroganos/goldflipper/wiki',
    },
)

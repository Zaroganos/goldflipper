from setuptools import setup, find_packages

# Load the README file as the long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name='goldflipper',
    version='0.2.2',
    author='Yaroshevskiy, Iliya',
    author_email='purpleafmanagement@gmail.com',
    description='A semi-autonomous options trading system on Alpaca.',
    long_description=long_description,             # Long description from README.md
    long_description_content_type="text/markdown",
    url='https://github.com/Zaroganos/goldflipper',
    license='Proprietary. Copyright Iliya Yaroshevskiy. All rights reserved.',

    # Automatically discover and include all packages and sub-packages
    packages=find_packages(),  

    # Include additional files specified in MANIFEST.in
    include_package_data=True,

    # Package data to include
    package_data={
        'goldflipper': [
            'tools/play-template.json',           # JSON Play template
            'config/*.py',                        # Configuration Management Module
            'config/settings_template.yaml',      # Settings template
        ],
    },

    # Suggested Python version compatibility
    python_requires='>=3.10',

    install_requires=[
        'alpaca-py>=0.40.0',              # Alpaca Markets brokerage trading API v2
        'yfinance>=0.2.54',               # Unofficial, free yahoo market data API
        'pandas>=2.0.0',
        'numpy>=1.24.0',
        'matplotlib>=3.7.0',              # Data visualization
        'seaborn>=0.12.0',                # Data visualization
        'scipy>=1.10.0',
        'ta>=0.10.0',                     # Technical analysis
        'textual>=1.0.0',                 # TUI
        'psutil>=5.9.0',                  # System monitoring
        'pytest>=7.0.0',
        'nest-asyncio>=1.5.0',            # Async library
        'pywin32',
        'tkinterdnd2>=0.3.0',             # Drag and drop support in the setup dialog
        'requests>=2.25.0',               # HTTP library for API communication
        'charset-normalizer>=3.2.0',      # Required for requests library
        'urllib3>=1.26.0',                # HTTP client
        'PyYAML>=6.0.1',                  # YAML parsing
        'colorama>=0.4.6',                # Terminal color output
        'rich>=13.0.0',                   # Enhanced terminal output
        'mplfinance>=0.12.10b0',           # Financial plotting (using beta version as stable 0.12.0 doesn't exist)
        'XlsxWriter>=3.1.0',              # Excel file creation
    ],

    # Entry points to cli tools or scripts
    entry_points={
        'console_scripts': [
            'goldflipper=goldflipper.run:main',
        ],
    },

    classifiers=[
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'License :: Other/Proprietary License',
        'Operating System :: Microsoft :: Windows',
        'Development Status :: 4 - Beta',
        'Intended Audience :: Internal Use Only',
        'Intended Audience :: Retail and Institutional Options Traders',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Office/Business :: Financial :: Investment',
    ],

    keywords='algorithmic trading alpaca finance stocks options',

    project_urls={
        'Bug Reports': 'https://github.com/Zaroganos/goldflipper/issues',
        'Source': 'https://github.com/Zaroganos/goldflipper',
        'Documentation': 'https://github.com/Zaroganos/goldflipper#readme'
    },
)

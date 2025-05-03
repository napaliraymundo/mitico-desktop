from setuptools import setup

APP = ['mitico-analysis.py']
OPTIONS = {
    'argv_emulation': False, # no terminal
    'iconfile': 'app.icns',
    'packages': ['PyQt5', 'numpy', 'pandas', 'matplotlib'],
}

setup(
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
from setuptools import setup

APP = ['Analysis.py']
OPTIONS = {
    'argv_emulation': False, # no terminal
    'iconfile': 'app.icns',
    'packages': ['PyQt5', 'numpy', 'pandas', 'matplotlib'],
     'excludes': [
        'tkinter', 'email', 'unittest', 'doctest', 'pydoc',
        'distutils', 'multiprocessing', 'sqlite3', 'http',
        'xml', 'logging', 'asyncio'
    ],
    'compressed': True,
    'optimize': 2
}

setup(
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
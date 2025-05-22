from setuptools import setup

APP = ['Analysis.py']
OPTIONS = {
    'argv_emulation': False, # no terminal
    'iconfile': 'app.icns',
    'packages': ['PyQt5', 'numpy', 'pandas', 'matplotlib', 'reportlab', 'scipy'],
    'compressed': True,
    'optimize': 2
}

setup(
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
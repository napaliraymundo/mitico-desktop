# mitico-desktop
Data Analysis App for Mitico Reactors
Download available in Github releases

Steps to compile and build app updates:
MAC
source venv/bin/activate
pip install pyqt5 pandas numpy matplotlib reportlab
pip install pyinstaller
python setup.py py2app

PC
venv\Scripts\activate
pip install pyqt5 pandas numpy matplotlib reportlab
pip install pyinstaller
pyinstaller Analysis.py ^
  --name Mitico ^
  --onefile ^
  --windowed ^
  --icon=icon.ico ^
  --hidden-import numpy.linalg ^
  --hidden-import pandas._libs.tslibs.timedeltas ^
  --hidden-import pandas._libs.window.aggregations

Builds are then found in the dist/ folder
# mitico-desktop

**Data Analysis App for Mitico Reactors**    
  [GitHub Repository](https://github.com/napaliraymundo/mitico-desktop)  
Download available in GitHub releases.

---

## Steps to Compile and Build App Updates

### On Mac

```bash
source venv/bin/activate
pip install pyqt5 pandas numpy matplotlib reportlab
pip install pyinstaller
python setup.py py2app
```

### On PC
```
venv\Scripts\activate
pip install pyqt5 pandas numpy matplotlib reportlab
pip install pyinstaller
pyinstaller  ^
  --name Mitico ^
  --onefile ^
  --windowed ^
  --icon=icon.ico ^
  --hidden-import numpy.linalg ^
  --hidden-import pandas._libs.tslibs.timedeltas ^
  --hidden-import pandas._libs.window.aggregations
  ```
  Builds are then located in dist/
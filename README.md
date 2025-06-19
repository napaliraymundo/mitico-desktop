# mitico-desktop

**Data Analysis App for Mitico Reactors**    
  [GitHub Repository](https://github.com/napaliraymundo/mitico-desktop)  
Download available in GitHub releases.

---
## Steps to Manually Compile and Build App Updates
(App automatically builds for PC on github push)

### On Mac

Download source code from github repository. Then in terminal:
```bash
cd /path-to-your-download
source venv/bin/activate
python -m pip install --upgrade pip
pip install pyinstaller
pip install -r requirements.txt
pyinstaller --onedir --windowed --icon=app.icns --add-data "run_parameters.csv:." Analysis.py 
```
Builds are then located in dist/

### On PC
Download source code from github repository. Then in Command Prompt:
```bash
cd \path-to-your-download
venv\Scripts\activate
pip install pyinstaller
pip install -r requirements.txt
pyinstaller --onedir --windowed --icon=app.icns --add-data "run_parameters.csv;." Analysis.py
  ```
Builds are then located in dist/
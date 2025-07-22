import sys
import os
import ast
os.environ['MPLCONFIGDIR'] = os.path.expanduser('~/.myapp_matplotlib_cache')

def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller bundle."""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def user_data_path(filename):
    """Return a user-writable path for persistent app data."""
    if sys.platform == "darwin":
        # macOS
        app_support = os.path.expanduser('~/Library/Application Support/Mitico')
    elif os.name == "nt":
        # Windows
        app_support = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'Mitico')
    else:
        # Linux/other
        app_support = os.path.expanduser('~/.mitico')
    if not os.path.exists(app_support):
        os.makedirs(app_support, exist_ok=True)
    return os.path.join(app_support, filename)

# On startup, ensure user copy of run_parameters.csv exists
BUNDLED_CSV = resource_path("run_parameters.csv")
USER_CSV = user_data_path("run_parameters.csv")
if not os.path.isfile(USER_CSV):
    try:
        import shutil
        shutil.copy(BUNDLED_CSV, USER_CSV)
    except Exception:
        # If copy fails (e.g., missing in bundle), just create empty file
        open(USER_CSV, 'a').close()

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QLabel, QListWidget,
    QVBoxLayout, QHBoxLayout, QFileDialog, QTabWidget, QGroupBox, QLineEdit, QComboBox
)
import pandas as pd
import csv
from DataViewer import DataViewer
from CapacityAnalysis import CapacityAnalysis
from TableViewer import TableViewer
from FileParsers import MassSpecParser, BackendParser, Baldy2Parser, save_pdf_report
from datetime import datetime
from RawDataViewer import RawDataViewer

class MyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        #Empty initializations and instantiate tab elements
        self.filename = ""
        self.mdf = pd.DataFrame()
        self.cycle_times_df = pd.DataFrame()
        self.compound_list = []
        self.reactor_parameters = []
        self.other_parameters = []
        self.status_text = ""
        self.status_error = ""
        self.sorbent_mass = ""
        self.reactor_diameter = ""
        self.bulk_density = ""
        self.packing_factor = ""
        self.reference_gas = ""
        self.reactor_input_ratio = ""
        self.input_flow_rate = ""
        self.qms_input_ratio = ""
        self.sorption_start = ""
        self.sorption_end = ""
        self.loaded_row = ""
        self.viewer_instance = DataViewer(self)
        self.metrics_instance = TableViewer(self)
        self.cycle_instance = CapacityAnalysis(self)
        self.raw_data_instance = RawDataViewer(self)


        # OTHER VARIABLES
        self.gas_abbr = {
            "":"",
            "Nitrogen": "N2",
            "Oxygen": "O2",
            "Argon": "Ar",
            "Helium": "He",
            "Hydrogen": "H2",
            "Carbon dioxide": "CO2",
        }

        self.build_layout()

    def check_run_parameters(self):
        """On text input change or data load, check values OK and see if changed"""
        if getattr(self, 'first_load', False):
            return
        #Reset status text, and default to no saving parameters
        self.parameter_status.setStyleSheet("")
        
        #Change detection for gas dropdown
        if self.reference_gas_dropdown.currentText() != self.reference_gas:
            #Mark that parameters have been changed
            self.parameter_status.setStyleSheet("")
            self.parameter_status.setText("Status: Run Parameters Changed")
            # Update label text for reactor input ratio
            abbr = self.gas_abbr[self.reference_gas_dropdown.currentText()]
            self.reactor_input_ratio_label.setText(f"Reactor Input Ratio (%)")
        
        #Change detection for text inputs
        inputs = [
        (self.sorbent_mass_input, 'sorbent_mass'),
        (self.reactor_diameter_input,'reactor_diameter'),
        (self.bulk_density_input,'bulk_density'),
        (self.packing_factor_input,'packing_factor'),
        (self.input_flow_rate_input, 'input_flow_rate'),
        (self.reactor_input_ratio_input, 'reactor_input_ratio'),
        (self.qms_input_ratio_input, 'qms_input_ratio'),
        (self.sorption_start_input, 'sorption_start'),
        (self.sorption_end_input, 'sorption_end'),
        ]
        for widget, attr_name in inputs:
            value = widget.text()
            try: #If the value is a valid float, detect change
                float(value)
                #If different than stored value, mark as changed and update value
                if value != getattr(self, attr_name):
                    self.parameter_status.setStyleSheet("")
                    self.parameter_status.setText("Status: Run Parameters Changed")
            except ValueError:
                #Throw error if not a number, disable graphs
                self.parameter_status.setStyleSheet("color: red")
                self.parameter_status.setText(f"Error: '{value}' is not a number")
                return False #Check run parameters fails

        # Always update instance variables from input widgets after validation
        for widget, attr_name in inputs:
            setattr(self, attr_name, widget.text())

        #Propagate changes and enable buttons if parameters OK
        if not self.first_load: self.update_all_calculations()
        return True
    
    def update_all_calculations(self):
        self.cycle_instance.cut_start()
        self.cycle_instance.cut_end()
        self.cycle_instance.calculate_secondary()
        self.cycle_instance.calculate_sorption()    
        self.cycle_instance.calculate_kinetics_wet()
        self.cycle_instance.calculate_kinetics_dry()
        self.cycle_instance.update_plots()
        self.viewer_instance.update_data()
        self.viewer_instance.update_plot()
        self.metrics_instance.reload_dropdown()
        self.metrics_instance.update_table()
        self.metrics_instance.update_plot()
        self.raw_data_instance.update_table()

    def update_cycles(self):
        self.cycle_instance.cut_start()
        self.cycle_instance.cut_end()
        self.cycle_instance.calculate_secondary()
        self.cycle_instance.calculate_sorption()    
        self.cycle_instance.calculate_kinetics_wet()
        self.cycle_instance.calculate_kinetics_dry()
        self.cycle_instance.update_plots()
        self.metrics_instance.update_table()
        self.metrics_instance.update_plot()

    def ensure_run_parameters_csv(self):
        """Ensure the run_parameters.csv exists and has the correct header."""
        csv_file = user_data_path("run_parameters.csv")
        expected_header = ["Filename"] + list(self.parameters.keys())
        file_exists = os.path.isfile(csv_file)
        header_ok = False
        if file_exists:
            with open(csv_file, mode="r", newline="") as file:
                reader = csv.reader(file)
                try:
                    header = next(reader)
                except StopIteration:
                    header = []
            if header == expected_header:
                header_ok = True
            else:
                # Remove file if header is wrong
                file.close()
                os.remove(csv_file)
                file_exists = False
        if not file_exists:
            with open(csv_file, mode="w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(expected_header)

    def load_run_parameters(self):
        """Load run parameters from a run_parameters.csv indexed by filename."""
        csv_file = user_data_path("run_parameters.csv")
        param_map = {
            "Sorbent Mass [g]": (self.sorbent_mass_input, "sorbent_mass", ''),
            "Reactor Diameter [in]": (self.reactor_diameter_input, "reactor_diameter", '0.8'),
            "Sorbent Bulk Density [g/mL]": (self.bulk_density_input, "bulk_density", ''),
            "Packing Factor": (self.packing_factor_input, "packing_factor", '0.55'),
            "Input Flow Rate [SCCM]": (self.input_flow_rate_input, "input_flow_rate", '150'),
            "Reactor Input Ratio (%)": (self.reactor_input_ratio_input, "reactor_input_ratio", '10'),
            "QMS Input Ratio (%)": (self.qms_input_ratio_input, "qms_input_ratio", ''),
            "Sorption Start (%)": (self.sorption_start_input, "sorption_start", '0.5'),
            "Sorption End (%)": (self.sorption_end_input, "sorption_end", '0.9'),
        }
        try:
            self.parameters = {
                "Save Timestamp": "",
                "Sorbent Mass [g]": "",
                "Reactor Diameter [in]": "",
                "Sorbent Bulk Density [g/mL]": "",
                "Input Flow Rate [SCCM]": "",
                "Packing Factor": "",
                "Reference Gas": "",
                "Reactor Input Ratio (%)": "",
                "QMS Input Ratio (%)": "",
                "Sorption Start (%)": "",
                "Sorption End (%)": "",
                "Selected Compounds": [],
                "Selected Parameters": [],
                "Selected Others": [],
                "Scale Run Graph": False,
                "Start Cuts": [],
                "End Cuts": [],
                "Cycle Plot Elements": [],
                "Scale Cycle Graph": False,
                "Selected Metrics:": []
            }
            self.ensure_run_parameters_csv()
            self.first_load = True  # Set before any field changes
            found_row = False
            if os.path.isfile(csv_file):
                with open(csv_file, mode="r") as file:
                    reader = csv.DictReader(file)
                    csv_filenames = [row["Filename"] for row in list(reader)]
                    # Debug print
                    print(f"[DEBUG] self.filename: {self.filename}, CSV filenames: {csv_filenames}")
                    file.seek(0)
                    next(reader)  # skip header
                    for row in list(reader)[::-1]:
                        if row["Filename"] == self.filename:
                            print('Found', row)
                            found_row = True
                            for key, (widget, attr, _) in param_map.items():
                                value = row.get(key, "")
                                widget.setText(value)
                                setattr(self, attr, value)
                                self._last_committed_values[widget] = value
                            ref_gas = row.get("Reference Gas", "")
                            self.reference_gas_dropdown.setCurrentText(ref_gas)
                            self.reference_gas = ref_gas
                            self.parameter_status.setText("Status: App State Loaded")
                            self.loaded_row = row
                            if len(list(ast.literal_eval(row.get('Start Cuts')))) == len(self.cycle_times_df):
                                self.cycle_times_df['Sorption Start Time'] = pd.to_datetime(list(ast.literal_eval(row.get('Start Cuts'))))
                                self.cycle_times_df['Sorption End Time'] = pd.to_datetime(list(ast.literal_eval(row.get('End Cuts'))))
                            break
            if not found_row:
                for _, (widget, attr, default) in param_map.items():
                    setattr(self, attr, default)
                    widget.setText(default)
                    self._last_committed_values[widget] = default
                self.reference_gas_dropdown.setCurrentText('Argon')
                self.reference_gas = 'Argon'
            self.first_load = False
            self.check_run_parameters()
        except Exception as e:
            pass

    def save_run_parameters(self):
        """Save run parameters to run_parameters.csv indexed by filename."""
        csv_file = user_data_path("run_parameters.csv")
        file_name = self.file_label.text()[6:]
        self.parameters = {
            "Save Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Sorbent Mass [g]": self.sorbent_mass_input.text(),
            "Reactor Diameter [in]": self.reactor_diameter_input.text(),
            "Sorbent Bulk Density [g/mL]": self.bulk_density_input.text(),
            "Input Flow Rate [SCCM]": self.input_flow_rate_input.text(),
            "Packing Factor": self.packing_factor_input.text(),
            "Reference Gas": self.reference_gas_dropdown.currentText(),
            "Reactor Input Ratio (%)": self.reactor_input_ratio_input.text(),
            "QMS Input Ratio (%)": self.qms_input_ratio_input.text(),
            "Sorption Start (%)": self.sorption_start_input.text(),
            "Sorption End (%)": self.sorption_end_input.text(),
            "Selected Compounds": [item.text() for item in self.viewer_instance.compound_list.selectedItems()],
            "Selected Parameters": [item.text() for item in self.viewer_instance.reactor_param_list.selectedItems()],
            "Selected Others": [item.text() for item in self.viewer_instance.other_param_list.selectedItems()],
            "Scale Run Graph": self.viewer_instance.scaling_checkbox.isChecked(),
            "Start Cuts": [str(dt) for dt in self.cycle_times_df['Sorption Start Time']],
            "End Cuts": [str(dt) for dt in self.cycle_times_df['Sorption End Time']],
            "Cycle Plot Elements": [item.text() for item in self.cycle_instance.ax1_param_list.selectedItems()],
            "Scale Cycle Graph": self.cycle_instance.scaling_checkbox.isChecked(),
            "Selected Metrics:": [item.text() for item in self.metrics_instance.param_list.selectedItems()]
        }
        try:
            self.ensure_run_parameters_csv()
            with open(csv_file, mode="a", newline="") as file:
                writer = csv.writer(file)
                writer.writerow([file_name] + list(self.parameters.values()))
            # Change status and propagate data
            self.load_run_parameters()
            self.viewer_instance.load_row()
            self.metrics_instance.load_row()
            self.cycle_instance.load_row()
            self.parameter_status.setText("Status: App State Saved")
        except Exception as e:
            pass
    
    def load_qms_data(self):
        """Load a QMS CSV file and propagate UI changes based on data"""
        if self.select_button.text() == "Load New QMS Data (Restart)": self.restart_analysis()

        #Find file
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open CSV File",
            "",
            "CSV Files (*.csv)",
            options=options
        )
        if file_name:
            self.filepath = file_name
            self.filename = f"{os.path.basename(file_name)}"
            try:
                self.parser = MassSpecParser(self)
                self.mdf, self.compound_list, self.cycle_times_df = self.parser.parse()
                self.reference_gas_dropdown.addItems(self.compound_list)
                self.file_label.setStyleSheet("")
                self.file_label.setText(f"File: {os.path.basename(file_name)}")
                self.file_label.setToolTip(file_name)
                self.time_label.setText(f"Datetime: {self.mdf.index[0]}")
                self.duration_label.setText(
                    f"Duration: {self.mdf.index[-1]-self.mdf.index[0]}")
                self.secondary_status.setEnabled(True)
                self.secondary_status.setStyleSheet("")
                self.secondary_status.setText("Status: No Secondary Loaded")
                self.run_parameters_groupbox.setEnabled(True)
                self.baldy2_button.setEnabled(True)
                self.baldy3_button.setEnabled(True)
                self.select_button.setText("Load New QMS Data (Restart)")
                self.load_run_parameters()
                self.viewer_instance.load_row()
                self.metrics_instance.load_row()
                self.cycle_instance.load_row()
                self.save_pdf_button.setEnabled(True)  # Enable PDF button when data is loaded
            except ValueError as e:
                self.file_label.setStyleSheet("color: red")
                self.file_label.setText(f"File: {e}")
                self.time_label.setText("Datetime:")
                self.duration_label.setText("Duration:")
                self.secondary_status.setEnabled(False)
                self.secondary_status.setText("Status: Waiting for QMS data load")
                self.parameter_status.setText("Status: Waiting for QMS data load")
                self.baldy2_button.setEnabled(False)
                self.baldy3_button.setEnabled(False)
                self.run_parameters_groupbox.setEnabled(False)

    def load_reactor_data(self):
        """Load a data folder from the Baldy3 backend and propagate UI changes"""
        self.secondary_status.setStyleSheet("")
        self.secondary_status.setText('Status: Loading')
        folder_path = QFileDialog.getExistingDirectory(None,"Select Folder","")
        if folder_path:
            try:
                #  TODO PASS THE INSTANCE INSTEAD TO BACKEND PARSER
                backend_parser = BackendParser(
                    self.mdf, self.time_label.text(), self.duration_label.text(), self.file_label.text()[6:], folder_path)
                self.mdf, self.reactor_parameters, self.cycle_times_df = backend_parser.parse()
                self.secondary_status.setStyleSheet("")
                self.secondary_status.setText('Status: Reactor data merge OK')
                self.baldy3_button.setEnabled(False)
                self.baldy2_button.setEnabled(False)
                self.load_run_parameters()
                self.viewer_instance.load_row()
                self.metrics_instance.load_row()
                self.cycle_instance.load_row()
            except ValueError as e:
                self.secondary_status.setStyleSheet("color: red")
                self.secondary_status.setText(f'Status: Folder invalid – Try another Folder')
        else: self.secondary_status.setText("Status: No Secondary File Loaded")

    def load_temp_data(self):
        """Load a temperature data CSV from the Baldy2 backend and propagate UI changes"""
        self.secondary_status.setStyleSheet("")
        self.secondary_status.setText('Status: Loading')
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open CSV File",
            "",
            "CSV Files (*.csv)",
            options=options
        )
        if file_name:
            try:
                baldy2_parser = Baldy2Parser(self.mdf, file_name)
                self.mdf, self.reactor_parameters = baldy2_parser.parse()
                self.secondary_status.setStyleSheet("")
                self.secondary_status.setText('Status: Temp data merge OK')
                self.baldy2_button.setEnabled(False)
                self.baldy3_button.setEnabled(False)
                self.load_run_parameters()
                self.viewer_instance.load_row()
                self.metrics_instance.load_row()
                self.cycle_instance.load_row()
            except ValueError as e:
                self.secondary_status.setStyleSheet("color: red")
                self.secondary_status.setText(f'Status: File invalid – Try another CSV')
        else: self.secondary_status.setText("Status: No Secondary File Loaded")


    def restart_analysis(self):        
        # Create new instances
        self.metrics_instance.param_list = None
        self.viewer_instance.other_param_list = None
        self.viewer_instance.reactor_param_list = None
        self.viewer_instance.compound_list = None
        self.viewer_instance = DataViewer(self)
        self.cycle_instance = CapacityAnalysis(self)
        self.metrics_instance = TableViewer(self)
        self.raw_data_instance = RawDataViewer(self)
        # Remove all tabs
        self.tabs.clear()

        # Add new tabs
        self.tabs.addTab(self.viewer_instance, "Run Graph")
        self.tabs.addTab(self.cycle_instance, "Cycle Graph")
        self.tabs.addTab(self.metrics_instance, "Cycle Metrics")
        self.tabs.addTab(self.raw_data_instance, "Raw Data")
        # Remove all items in reference_gas_dropdown
        self.reference_gas_dropdown.clear()


    def build_layout(self):
        self.setWindowTitle("Mitico Data Analysis")
        # Remove global stylesheet
        self.screen_geometry = QApplication.desktop().availableGeometry()
        self.setGeometry(0, 0, self.screen_geometry.width(), self.screen_geometry.height())

        # Central widget
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Main layout
        self.main_layout = QHBoxLayout()
        toolbox_widget = QWidget()
        toolbox_widget.setFixedWidth(300)
        toolbox_layout = QVBoxLayout()
        toolbox_layout.setSpacing(10)  # Increase vertical spacing between widgets
        toolbox_layout.setContentsMargins(6, 6, 6, 6)  # Keep margins
        self.viewer_widget = QWidget()
        self.viewer_layout = QVBoxLayout()
    
        # LOAD QMS SECTION
        self.select_button = QPushButton("Load QMS Data")
        self.file_label = QLabel("File: ")
        self.time_label = QLabel("Start Date: ")
        self.duration_label = QLabel("Run Duration: ")

        qms_groupbox_layout = QVBoxLayout()
        qms_groupbox_layout.setSpacing(8)
        qms_groupbox_layout.setContentsMargins(4, 4, 4, 4)
        qms_groupbox_layout.addWidget(self.select_button)
        qms_groupbox_layout.addWidget(self.file_label)
        qms_groupbox_layout.addWidget(self.time_label)
        qms_groupbox_layout.addWidget(self.duration_label)

        qms_groupbox = QGroupBox("QMS File Management")
        qms_groupbox.setLayout(qms_groupbox_layout)
        toolbox_layout.addWidget(qms_groupbox)

        # LOAD OTHER DATA SECTION
        self.baldy3_button = QPushButton("Baldy3: Load Data Folder")
        self.baldy3_button.setEnabled(False)
        self.baldy2_button = QPushButton("Baldy2: Load Temperature Data")
        self.baldy2_button.setEnabled(False)
        self.secondary_status = QLabel("Status: Waiting for QMS data load")
        self.secondary_status.setEnabled(False)

        sensor_groupbox = QGroupBox("Secondary File Management")
        sensor_groupbox_layout = QVBoxLayout()
        sensor_groupbox_layout.setSpacing(8)
        sensor_groupbox_layout.setContentsMargins(4, 4, 4, 4)
        sensor_groupbox_layout.addWidget(self.baldy3_button)
        sensor_groupbox_layout.addWidget(self.baldy2_button)
        sensor_groupbox_layout.addWidget(self.secondary_status)

        sensor_groupbox.setLayout(sensor_groupbox_layout)
        toolbox_layout.addWidget(sensor_groupbox)
        

        # RUN PARAMETERS SECTION
        self.sorbent_mass_input = QLineEdit()
        self.reactor_diameter_input = QLineEdit()
        self.bulk_density_input = QLineEdit()
        self.packing_factor_input = QLineEdit()
        self.reactor_input_ratio_input = QLineEdit()
        self.reference_gas_dropdown = QComboBox()
        self.input_flow_rate_input = QLineEdit()
        self.qms_input_ratio_input = QLineEdit()
        self.sorption_start_input = QLineEdit()
        self.sorption_end_input = QLineEdit()

        self.run_parameters_groupbox = QGroupBox("Run Parameters")
        run_parameters_layout = QVBoxLayout()
        run_parameters_layout.setSpacing(8)
        run_parameters_layout.setContentsMargins(4, 4, 4, 4)

        sorbent_mass_layout = QHBoxLayout()
        sorbent_mass_label = QLabel("Sorbent Mass [g]:")
        sorbent_mass_layout.addWidget(sorbent_mass_label)
        sorbent_mass_layout.addWidget(self.sorbent_mass_input)
        run_parameters_layout.addLayout(sorbent_mass_layout)

        reactor_diameter_layout = QHBoxLayout()
        reactor_diameter_label = QLabel("Reactor Diameter [in]:")
        reactor_diameter_layout.addWidget(reactor_diameter_label)
        reactor_diameter_layout.addWidget(self.reactor_diameter_input)
        run_parameters_layout.addLayout(reactor_diameter_layout)

        bulk_density_layout = QHBoxLayout()
        bulk_density_label = QLabel("Sorbent Bulk Density [g/mL]:")
        bulk_density_layout.addWidget(bulk_density_label)
        bulk_density_layout.addWidget(self.bulk_density_input)
        run_parameters_layout.addLayout(bulk_density_layout)

        packing_factor_layout = QHBoxLayout()
        packing_factor_label = QLabel("Packing Factor:")
        packing_factor_layout.addWidget(packing_factor_label)
        packing_factor_layout.addWidget(self.packing_factor_input)
        run_parameters_layout.addLayout(packing_factor_layout)

        reference_gas_layout = QHBoxLayout()
        reference_gas_label = QLabel("Reference Gas:")
        reference_gas_layout.addWidget(reference_gas_label)
        reference_gas_layout.addWidget(self.reference_gas_dropdown)
        run_parameters_layout.addLayout(reference_gas_layout)

        input_flow_rate_layout = QHBoxLayout()
        input_flow_rate_label = QLabel("Input Flow Rate [SCCM]")
        input_flow_rate_layout.addWidget(input_flow_rate_label)
        input_flow_rate_layout.addWidget(self.input_flow_rate_input)
        run_parameters_layout.addLayout(input_flow_rate_layout)

        reactor_input_ratio_layout = QHBoxLayout()
        self.reactor_input_ratio_label = QLabel("Reactor Input Ratio (%)")
        reactor_input_ratio_layout.addWidget(self.reactor_input_ratio_label)
        reactor_input_ratio_layout.addWidget(self.reactor_input_ratio_input)
        run_parameters_layout.addLayout(reactor_input_ratio_layout)

        qms_input_ratio_layout = QHBoxLayout()
        qms_input_ratio_label = QLabel("QMS Input Ratio (%):")
        qms_input_ratio_layout.addWidget(qms_input_ratio_label)
        qms_input_ratio_layout.addWidget(self.qms_input_ratio_input)
        run_parameters_layout.addLayout(qms_input_ratio_layout)

        sorption_start_layout = QHBoxLayout()
        sorption_start_label = QLabel("Sorption Start (%):")
        sorption_start_layout.addWidget(sorption_start_label)
        sorption_start_layout.addWidget(self.sorption_start_input)
        run_parameters_layout.addLayout(sorption_start_layout)

        sorption_end_layout = QHBoxLayout()
        sorption_end_label = QLabel("Sorption End (%):")
        sorption_end_layout.addWidget(sorption_end_label)
        sorption_end_layout.addWidget(self.sorption_end_input)
        run_parameters_layout.addLayout(sorption_end_layout)

        self.parameter_status = QLabel("Status: Waiting for QMS data load")
        run_parameters_layout.addWidget(self.parameter_status)

        self.run_parameters_groupbox.setLayout(run_parameters_layout)
        self.run_parameters_groupbox.setEnabled(False)
        toolbox_layout.addWidget(self.run_parameters_groupbox)

        # RUN ANALYSIS SECTION
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.addTab(self.viewer_instance, "Run Graph")
        self.tabs.addTab(self.cycle_instance,"Cycle Graph")
        self.tabs.addTab(self.metrics_instance, "Cycle Metrics")
        self.tabs.addTab(self.raw_data_instance, "Raw Data")

        self.save_parameters_button = QPushButton("Save App State")
        self.save_pdf_button = QPushButton("Save Full PDF Report")
        self.save_pdf_button.setEnabled(False)

        analysis_groupbox = QGroupBox("Program Functions")
        analysis_layout = QVBoxLayout()
        analysis_layout.setSpacing(8)
        analysis_layout.setContentsMargins(4, 4, 4, 4)
        analysis_layout.addWidget(self.save_pdf_button)
        analysis_layout.addWidget(self.save_parameters_button)

        analysis_groupbox.setLayout(analysis_layout)
        toolbox_layout.addWidget(analysis_groupbox)

        # FINALIZE LAYOUT
        toolbox_layout.addStretch()
        toolbox_widget.setLayout(toolbox_layout)
        self.viewer_widget.setLayout(self.viewer_layout)
        self.main_layout.addWidget(toolbox_widget)
        self.main_layout.addWidget(self.tabs, stretch=1)
        self.central_widget.setLayout(self.main_layout)

        # LINK BUTTON ON CLICK
        self.select_button.clicked.connect(self.load_qms_data)
        self.baldy3_button.clicked.connect(self.load_reactor_data)
        self.baldy2_button.clicked.connect(self.load_temp_data)
        self.save_parameters_button.clicked.connect(self.save_run_parameters)
        self.save_pdf_button.clicked.connect(lambda: save_pdf_report(self))

        self.reference_gas_dropdown.currentIndexChanged.connect(self.check_run_parameters)
        #Store last committed values for each QLineEdit
        self._last_committed_values = {
            self.sorbent_mass_input: '',
            self.reactor_diameter_input: '',
            self.bulk_density_input: '',
            self.packing_factor_input: '',
            self.input_flow_rate_input: '',
            self.reactor_input_ratio_input: '',
            self.qms_input_ratio_input: '',
            self.sorption_start_input: '',
            self.sorption_end_input: '',
        }
        #Connect editingFinished for QLineEdits to custom handler
        for widget in self._last_committed_values:
            widget.editingFinished.connect(lambda w=widget: self._on_editing_finished(w))

    def _on_editing_finished(self, widget):
        current_value = widget.text()
        last_value = self._last_committed_values.get(widget, None)
        if current_value != last_value:
            self._last_committed_values[widget] = current_value
            self.check_run_parameters()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())
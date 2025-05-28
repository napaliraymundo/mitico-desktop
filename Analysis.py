import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QLabel,
    QVBoxLayout, QHBoxLayout, QFileDialog, QTabWidget, QGroupBox, QLineEdit, QMessageBox, QComboBox
)
import pandas as pd
import numpy as np
import csv
from DataViewer import DataViewer
from CapacityAnalysis import CapacityAnalysis
from TableViewer import TableViewer
from FileParsers import MassSpecParser, BackendParser, Baldy2Parser
from datetime import datetime
from RawDataViewer import RawDataViewer
from matplotlib.figure import Figure
import io
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Image, Spacer, Paragraph, PageBreak, KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

class MyApp(QMainWindow):
    def __init__(self):
        super().__init__()
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
        self.parameters_saved_text = "Status: Reactor Parameters Loaded"
        self.viewer_instance = DataViewer(self)
        self.metrics_instance = TableViewer(self)
        self.cycle_instance = CapacityAnalysis(self)
        self.raw_data_instance = RawDataViewer(self)


        # OTHER VARIABLES
        self.gas_abbr = {
            "Nitrogen": "N2",
            "Oxygen": "O2",
            "Argon": "Ar",
            "Helium": "He",
            "Hydrogen": "H2",
            "Carbon dioxide": "CO2",
        }

        self.build_layout()

    def load_run_parameters(self):
        """Load run parameters from a run_parameters.csv indexed by filename."""
        csv_file = "run_parameters.csv"
        try:
            self.first_load = True  # Set before any field changes
            #Try to open and parse the file
            if os.path.isfile(csv_file):
                with open(csv_file, mode="r") as file:
                    reader = csv.DictReader(file)
                    #Flip the order of the rows to get most recent save
                    for row in list(reader)[::-1]:
                        #Find correct file entry and read values into input boxes and self params
                        if row["Filename"] == self.filename:
                            # Define mapping of CSV keys to (input widget, attribute name)
                            param_map = {
                                "Sorbent Mass [g]": (self.sorbent_mass_input, "sorbent_mass"),
                                "Reactor Diameter [in]": (self.reactor_diameter_input, "reactor_diameter"),
                                "Sorbent Bulk Density [g/mL]": (self.bulk_density_input, "bulk_density"),
                                "Packing Factor": (self.packing_factor_input, "packing_factor"),
                                "Input Flow Rate [SCCM]": (self.input_flow_rate_input, "input_flow_rate"),
                                "Reactor Input Ratio (%)": (self.reactor_input_ratio_input, "reactor_input_ratio"),
                                "QMS Input Ratio (%)": (self.qms_input_ratio_input, "qms_input_ratio"),
                                "Sorption Start (%)": (self.sorption_start_input, "sorption_start"),
                                "Sorption End (%)": (self.sorption_end_input, "sorption_end"),
                            }
                            for key, (widget, attr) in param_map.items():
                                value = row.get(key, "")
                                widget.setText(value)
                                setattr(self, attr, value)
                                self._last_committed_values[widget] = value
                            # Handle reference gas separately (QComboBox)
                            ref_gas = row.get("Reference Gas", "")
                            self.reference_gas_dropdown.setCurrentText(ref_gas)
                            self.reference_gas = ref_gas
                            break #Once appropriate row has been found, stop iterating
            #Defaults for empty load
            if self.packing_factor_input.text() == '': 
                self.packing_factor_input.setText('0.55')
                self.packing_factor = '0.55'
            if self.reactor_diameter_input.text() == '':
                self.reactor_diameter_input.setText('0.8')
                self.reactor_diameter = '0.8'
            # Now call check_run_parameters once after all fields are set
            self.first_load = False
            self.check_run_parameters()
        except Exception as e:
            pass

    def check_run_parameters(self):
        """On text input change or data load, check values OK and see if changed"""
        if getattr(self, 'first_load', False):
            return
        #Reset status text, and default to no saving parameters
        self.parameter_status.setStyleSheet("")
        self.parameter_status.setText(self.parameters_saved_text)
        self.save_parameters_button.setEnabled(False)
        
        #Change detection for gas dropdown
        if self.reference_gas_dropdown.currentText() != self.reference_gas:
            #Mark that parameters have been changed
            self.save_parameters_button.setEnabled(True)
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
                    self.save_parameters_button.setEnabled(True)
                    self.parameter_status.setStyleSheet("")
                    self.parameter_status.setText("Status: Run Parameters Changed")
            except ValueError:
                #Throw error if not a number, disable graphs
                self.save_parameters_button.setEnabled(False)
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
        self.cycle_instance.calculate_secondary()
        self.cycle_instance.calculate_sorption()
        self.cycle_instance.calculate_kinetics()
        self.cycle_instance.update_plots()
        self.viewer_instance.update_data()
        self.viewer_instance.update_plot()
        self.metrics_instance.reload_dropdown()
        self.metrics_instance.update_table()
        self.metrics_instance.update_plot()
        self.raw_data_instance.update_table()

    def save_run_parameters(self):
        """Save run parameters to run_parameters.csv indexed by filename."""
        csv_file = "run_parameters.csv"
        file_name = self.file_label.text()[6:]
        parameters = {
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
            "Sorption End (%)": self.sorption_end_input.text()
        }
        try:
            # Check if the file exists
            file_exists = os.path.isfile(csv_file)
            # Make file if it's not present
            if not file_exists: 
                with open(csv_file, mode="w", newline="") as file:
                    pass
            # Open and write to the file
            with open(csv_file, mode="a", newline="") as file:
                writer = csv.writer(file)
                # Write header if the file is new
                if not file_exists:
                    writer.writerow(["Filename"] + list(parameters.keys()))
                # Write the parameters
                writer.writerow([file_name] + list(parameters.values()))
            # Change status and propagate data
            self.parameters_saved_text = "Status: Run Parameters Changed"
            self.load_run_parameters()
        except Exception as e:
            pass
    
    def load_qms_data(self):
        """Load a QMS CSV file and propagate UI changes based on data"""
        if self.select_button.text() == "Load New QMS Data (Restart)": self.restart_analysis()

        #Fine file
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
                self.check_run_parameters()
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
                self.check_run_parameters()
            except ValueError as e:
                self.secondary_status.setStyleSheet("color: red")
                self.secondary_status.setText(f'Status: File invalid – Try another CSV')
        else: self.secondary_status.setText("Status: No Secondary File Loaded")


    def restart_analysis(self):
        """Close the application and make a fresh instance"""
        ##Need to implement
        

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
        self.save_parameters_button = QPushButton("Save Run Parameters")

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

        run_parameters_layout.addWidget(self.save_parameters_button)

        self.parameter_status = QLabel("Status: Waiting for QMS data load")
        run_parameters_layout.addWidget(self.parameter_status)

        self.run_parameters_groupbox.setLayout(run_parameters_layout)
        self.run_parameters_groupbox.setEnabled(False)
        toolbox_layout.addWidget(self.run_parameters_groupbox)

        # RUN ANALYSIS SECTION
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.addTab(self.viewer_instance, "Graph Run")
        self.tabs.addTab(self.cycle_instance,"Graph Cycle")
        self.tabs.addTab(self.metrics_instance, "View Metrics")
        self.tabs.addTab(self.raw_data_instance, "Raw Data")

        self.save_pdf_button = QPushButton("Save Full PDF Report")
        self.save_pdf_button.setEnabled(False)

        analysis_groupbox = QGroupBox("Program Functions")
        analysis_layout = QVBoxLayout()
        analysis_layout.setSpacing(8)
        analysis_layout.setContentsMargins(4, 4, 4, 4)
        analysis_layout.addWidget(self.save_pdf_button)

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
        self.save_pdf_button.clicked.connect(self.save_pdf_report)

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

    def save_pdf_report(self):
        """Export a PDF report with run parameters, cycle_times_df, and all current plot images."""
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak, KeepTogether
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet
        import io

        # Prompt user for save location
        from PyQt5.QtWidgets import QFileDialog
        file_path, _ = QFileDialog.getSaveFileName(self, "Save PDF Report", f"{self.filename} Exp Report.pdf", "PDF Files (*.pdf)")
        if not file_path:
            return
        if not file_path.lower().endswith('.pdf'):
            file_path += '.pdf'

        # Prepare document
        page_width, page_height = letter
        left_margin = right_margin = top_margin = bottom_margin = 24
        doc = SimpleDocTemplate(
            file_path,
            pagesize=letter,
            leftMargin=left_margin,
            rightMargin=right_margin,
            topMargin=top_margin,
            bottomMargin=bottom_margin
        )
        elements = []
        styles = getSampleStyleSheet()
        styleN = styles['Normal']
        styleH = styles['Heading2']

        # 1. Run Parameters Table with header row
        elements.append(Paragraph("Run Parameters", styleH))
        param_map = [
            ("Sorbent Mass [g]", self.sorbent_mass_input.text()),
            ("Reactor Diameter [in]", self.reactor_diameter_input.text()),
            ("Sorbent Bulk Density [g/mL]", self.bulk_density_input.text()),
            ("Packing Factor", self.packing_factor_input.text()),
            ("Input Flow Rate [SCCM]", self.input_flow_rate_input.text()),
            ("Reference Gas", self.reference_gas_dropdown.currentText()),
            ("Reactor Input Ratio (%)", self.reactor_input_ratio_input.text()),
            ("QMS Input Ratio (%)", self.qms_input_ratio_input.text()),
            ("Sorption Start (%)", self.sorption_start_input.text()),
            ("Sorption End (%)", self.sorption_end_input.text()),
        ]
        param_table_data = [["Parameter", "Value"]] + [[k, v] for k, v in param_map]
        param_table = Table(param_table_data, hAlign='LEFT', colWidths=[160, 80])
        param_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        elements.append(param_table)
        elements.append(Spacer(1, 12))

        # 2. cycle_times_df Table (vertical, 5 cycles per table, 3 sig figs, sci notation, short datetimes, wide metric col)
        if self.cycle_times_df is not None and not self.cycle_times_df.empty:
            elements.append(Paragraph("Cycle Times Table", styleH))
            df = self.cycle_times_df.reset_index(drop=True)
            import pandas as pd
            def fmt(x, col=None):
                if isinstance(x, float):
                    return f"{x:.2e}" if x != 0 else "0"
                if col == 'Sorption Duration':
                    # Format timedelta as HH:MM:SS
                    try:
                        if pd.isnull(x):
                            return ""
                        if isinstance(x, pd.Timedelta):
                            total_seconds = int(x.total_seconds())
                        else:
                            total_seconds = int(pd.to_timedelta(x).total_seconds())
                        hours = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        seconds = total_seconds % 60
                        return f"{hours:02}:{minutes:02}:{seconds:02}"
                    except Exception:
                        return str(x)
                if isinstance(x, pd.Timestamp) or (hasattr(x, 'isoformat') and 'T' in str(x)):
                    try:
                        return pd.to_datetime(x).strftime('%H:%M:%S')
                    except Exception:
                        return str(x)
                if isinstance(x, str) and (':' in x and '-' in x):
                    try:
                        return pd.to_datetime(x).strftime('%H:%M:%S')
                    except Exception:
                        return x
                return str(x)
            n_cycles = df.shape[0]
            col_names = [str(c) for c in df.columns]
            for start in range(0, n_cycles, 5):
                end = min(start+5, n_cycles)
                cycles = df.iloc[start:end]
                header = ["Metric"] + [f"Cycle {int(c)}" for c in cycles['Cycle']]
                data = [header]
                for col in col_names:
                    if col == 'Cycle':
                        continue
                    row = [col]
                    for i in range(start, end):
                        val = df.at[i, col]
                        row.append(fmt(val, col=col))
                    data.append(row)
                for row in data:
                    while len(row) < 6:
                        row.append("")
                table = Table(data, hAlign='LEFT', colWidths=[200]+[60]*5, repeatRows=1)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ]))
                elements.append(table)
                elements.append(Spacer(1, 8))

        # 3. All current plot images (including all cycles in cycle viewer)
        buffers = []  # Keep references to all image buffers until PDF is built
        full_plot_width = page_width - left_margin - right_margin
        full_plot_height = full_plot_width * 0.45  # Slightly shorter to fit two per page
        if hasattr(self, 'cycle_instance') and self.cycle_instance is not None:
            try:
                figures = self.cycle_instance.get_all_figures_for_pdf()
            except Exception:
                figures = []
            if figures:
                elements.append(Paragraph("Cycle Analysis Plots", styleH))
                plot_pairs = [figures[i:i+2] for i in range(0, len(figures), 2)]
                for pair in plot_pairs:
                    imgs = []
                    for fig in pair:
                        for ax in fig.get_axes():
                            for item in ([ax.title, ax.xaxis.label, ax.yaxis.label] + ax.get_xticklabels() + ax.get_yticklabels() + ax.get_legend().get_texts() if ax.get_legend() else []):
                                item.set_fontsize(8)
                        buf = io.BytesIO()
                        fig.set_size_inches(full_plot_width / 96, full_plot_height / 96)
                        fig.savefig(buf, format='png', bbox_inches='tight', dpi=96)
                        buf.seek(0)
                        img = Image(buf, width=full_plot_width, height=full_plot_height)
                        imgs.append(img)
                        buffers.append(buf)
                    elements.append(KeepTogether(imgs))
                    elements.append(Spacer(1, 12))
                    elements.append(PageBreak())

        # Add DataViewer plot if available (make it full page)
        if hasattr(self, 'viewer_instance') and self.viewer_instance is not None:
            try:
                fig = self.viewer_instance.figure
                for ax in fig.get_axes():
                    for item in ([ax.title, ax.xaxis.label, ax.yaxis.label] + ax.get_xticklabels() + ax.get_yticklabels() + ax.get_legend().get_texts() if ax.get_legend() else []):
                        item.set_fontsize(8)
                buf = io.BytesIO()
                fig.set_size_inches(full_plot_width / 96, (full_plot_width * 0.6) / 96)
                fig.savefig(buf, format='png', bbox_inches='tight', dpi=96)
                buf.seek(0)
                img = Image(buf, width=full_plot_width, height=full_plot_width * 0.6)
                elements.append(Paragraph("Full Run Data Plot", styleH))
                elements.append(img)
                elements.append(Spacer(1, 12))
                buffers.append(buf)
                elements.append(PageBreak())
            except Exception:
                pass

        # Add MetricsViewer plot if available (make it full page)
        if hasattr(self, 'metrics_instance') and self.metrics_instance is not None:
            try:
                fig = self.metrics_instance.figure
                for ax in fig.get_axes():
                    for item in ([ax.title, ax.xaxis.label, ax.yaxis.label] + ax.get_xticklabels() + ax.get_yticklabels() + ax.get_legend().get_texts() if ax.get_legend() else []):
                        item.set_fontsize(8)
                buf = io.BytesIO()
                fig.set_size_inches(full_plot_width / 96, (full_plot_width * 0.6) / 96)
                fig.savefig(buf, format='png', bbox_inches='tight', dpi=96)
                buf.seek(0)
                img = Image(buf, width=full_plot_width, height=full_plot_width * 0.6)
                elements.append(Paragraph("Metrics Table Plot", styleH))
                elements.append(img)
                elements.append(Spacer(1, 12))
                buffers.append(buf)
                # Only add a PageBreak if this is not the last element
                # Remove the unconditional PageBreak here
            except Exception:
                pass

        # Remove trailing PageBreak if present
        if elements and isinstance(elements[-1], PageBreak):
            elements = elements[:-1]

        # Build PDF
        try:
            doc.build(elements)
        except Exception as e:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self, "PDF Export Error", f"Failed to save PDF: {e}")
            return
        finally:
            for buf in buffers:
                buf.close()

        # Success message
        from PyQt5.QtWidgets import QMessageBox
        QMessageBox.information(self, "PDF Exported", f"PDF report saved to:\n{file_path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())
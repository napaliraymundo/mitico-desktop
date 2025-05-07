import sys
import os
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QPushButton, QLabel,
    QVBoxLayout, QHBoxLayout, QFileDialog, QSizePolicy, QGroupBox, QLineEdit
)
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import csv
from io import StringIO
from DataViewer import DataViewer
from FileParsers import MassSpecParser, BackendParser
            
class MyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mitico Data Analysis")
        screen_geometry = QApplication.desktop().screenGeometry()
        self.setGeometry(0, 0, 300, screen_geometry.height())
        self.setFixedWidth(300)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout()

        # LOAD QMS SECTION
        self.select_button = QPushButton("Load QMS Data")
        self.file_label = QLabel("File: ")
        self.time_label = QLabel("Start Date: ")
        self.duration_label = QLabel("Run Duration: ")

        qms_groupbox_layout = QVBoxLayout()
        qms_groupbox_layout.addWidget(self.select_button)
        qms_groupbox_layout.addWidget(self.file_label)
        qms_groupbox_layout.addWidget(self.time_label)
        qms_groupbox_layout.addWidget(self.duration_label)

        qms_groupbox = QGroupBox("QMS File Management")
        qms_groupbox.setLayout(qms_groupbox_layout)
        main_layout.addWidget(qms_groupbox)

        # LOAD OTHER DATA SECTION
        self.baldy3_button = QPushButton("Baldy3: Load Reactor Data")
        self.baldy3_button.setEnabled(False)
        self.baldy2_button = QPushButton("Baldy2: Load Temp Data")
        self.baldy2_button.setEnabled(False)
        self.secondary_status = QLabel("Status: ")

        sensor_groupbox = QGroupBox("Secondary File Management")
        sensor_groupbox_layout = QVBoxLayout()
        sensor_groupbox_layout.addWidget(self.baldy3_button)
        sensor_groupbox_layout.addWidget(self.baldy2_button)
        sensor_groupbox_layout.addWidget(self.secondary_status)

        sensor_groupbox.setLayout(sensor_groupbox_layout)
        main_layout.addWidget(sensor_groupbox)

        # RUN PARAMETERS SECTION
        self.sorbent_mass_input = QLineEdit()
        self.reactor_diameter_input = QLineEdit()
        self.bulk_density_input = QLineEdit()
        self.packing_factor_input = QLineEdit()
        self.qms_input_ratio_input = QLineEdit()

        self.run_parameters_groupbox = QGroupBox("Run Parameters")
        run_parameters_layout = QVBoxLayout()

        sorbent_mass_layout = QHBoxLayout()
        sorbent_mass_label = QLabel("Sorbent Mass (g):")
        sorbent_mass_layout.addWidget(sorbent_mass_label)
        sorbent_mass_layout.addWidget(self.sorbent_mass_input)
        run_parameters_layout.addLayout(sorbent_mass_layout)

        reactor_diameter_layout = QHBoxLayout()
        reactor_diameter_label = QLabel("Reactor Diameter (in):")
        reactor_diameter_layout.addWidget(reactor_diameter_label)
        reactor_diameter_layout.addWidget(self.reactor_diameter_input)
        run_parameters_layout.addLayout(reactor_diameter_layout)

        bulk_density_layout = QHBoxLayout()
        bulk_density_label = QLabel("Sorbent Bulk Density (g/mL):")
        bulk_density_layout.addWidget(bulk_density_label)
        bulk_density_layout.addWidget(self.bulk_density_input)
        run_parameters_layout.addLayout(bulk_density_layout)

        packing_factor_layout = QHBoxLayout()
        packing_factor_label = QLabel("Packing Factor:")
        packing_factor_layout.addWidget(packing_factor_label)
        packing_factor_layout.addWidget(self.packing_factor_input)
        run_parameters_layout.addLayout(packing_factor_layout)

        qms_input_ratio_layout = QHBoxLayout()
        qms_input_ratio_label = QLabel("QMS Input Ratio (baseline):")
        qms_input_ratio_layout.addWidget(qms_input_ratio_label)
        qms_input_ratio_layout.addWidget(self.qms_input_ratio_input)
        run_parameters_layout.addLayout(qms_input_ratio_layout)

        self.run_parameters_groupbox.setLayout(run_parameters_layout)
        self.run_parameters_groupbox.setEnabled(False)
        main_layout.addWidget(self.run_parameters_groupbox)

        # RUN ANALYSIS SECTION
        self.viewer_button = QPushButton("Launch Viewer")
        self.viewer_button.setEnabled(False)
        self.capacity_button = QPushButton("Run Capacity Analysis")
        self.kinetics_button = QPushButton("Run Kinetics Analysis")

        analysis_groupbox = QGroupBox("Execute Analysis")
        analysis_layout = QVBoxLayout()
        analysis_layout.addWidget(self.viewer_button)
        analysis_layout.addWidget(self.capacity_button)
        analysis_layout.addWidget(self.kinetics_button)

        analysis_groupbox.setLayout(analysis_layout)
        main_layout.addWidget(analysis_groupbox)

        # SAVE ANALYSIS SECTION
        self.save_csv_button = QPushButton("Save CSV")
        self.save_images_button = QPushButton("Save Plots")
        self.save_pdf_button = QPushButton("Save PDF Report")
        self.restart_button = QPushButton("Restart Analysis")

        save_groupbox = QGroupBox("Analysis Management")
        save_layout = QVBoxLayout()
        save_layout.addWidget(self.save_csv_button)
        save_layout.addWidget(self.save_images_button)
        save_layout.addWidget(self.save_pdf_button)
        save_layout.addWidget(self.restart_button)

        save_groupbox.setLayout(save_layout)
        main_layout.addWidget(save_groupbox)

        # FINALIZE LAYOUT
        main_layout.addStretch()
        central_widget.setLayout(main_layout)

        # LINK BUTTON ON CLICK
        self.select_button.clicked.connect(self.load_qms_data)
        self.baldy3_button.clicked.connect(self.load_reactor_data)
        # self.baldy2_button.clicked.connect(self.load_temp_data)
        self.viewer_button.clicked.connect(self.launch_viewer)
        # self.capacity_button.clicked.connect(self.run_capacity_analysis)
        # self.kinetics_button.clicked.connect(self.run_kinetics_analysis)
        # self.save_csv_button.clicked.connect(self.save_csv)
        # self.save_images_button.clicked.connect(self.save_plots)
        # self.save_pdf_button.clicked.connect(self.save_pdf_report)
        # self.restart_button.clicked.connect(self.restart_analysis)

        # OTHER VARIABLES
        self.mdf = []
        self.compound_list = []
        self.reactor_parameters = []
        self.other_parameters = []
        self.viewer_instance = None  # Add a reference to the viewer instance

    def load_qms_data(self):
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
                parser = MassSpecParser(file_name)
                self.mdf, self.compound_list = parser.parse()
                self.file_label.setStyleSheet("color: white")
                self.file_label.setText(f"File: {os.path.basename(file_name)}")
                self.file_label.setToolTip(file_name)
                self.time_label.setText(f"Datetime: {self.mdf.index[0]}")
                self.duration_label.setText(
                    f"Duration: {self.mdf.index[-1]-self.mdf.index[0]}")
                self.secondary_status.setStyleSheet("color: white")
                self.secondary_status.setText("Status: ")
                self.run_parameters_groupbox.setEnabled(True)
                self.baldy2_button.setEnabled(True)
                self.baldy3_button.setEnabled(True)
                self.viewer_button.setEnabled(True)
            except ValueError as e:
                self.file_label.setStyleSheet("color: red")
                self.file_label.setText(f"File: {e}")

    def load_reactor_data(self):
        try:
            backend_parser = BackendParser(
                self.mdf, self.time_label.text(), self.duration_label.text())
            self.mdf, self.reactor_parameters, self.cycle_times_df, self.cycle_times = backend_parser.parse()
            self.secondary_status.setStyleSheet("color: white")
            self.secondary_status.setText(f'Status: Reactor data merged')
            self.baldy2_button.setEnabled(False)
            self.baldy2_button.setStyleSheet("color: grey")
        except ValueError as e:
            self.secondary_status.setStyleSheet("color: red")
            self.secondary_status.setText(f'Status: {e}')

    def launch_viewer(self):
        if self.viewer_instance is None or not self.viewer_instance.isVisible():
            self.viewer_instance = DataViewer(self.mdf, self.reactor_parameters, self.compound_list, self.other_parameters)
            self.viewer_instance.show()
        else:
            self.viewer_instance.raise_()
            self.viewer_instance.activateWindow()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())

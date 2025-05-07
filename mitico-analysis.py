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


class MassSpecParser:
    def __init__(self, filename):
        self.filename = filename
        self.header_row_number = None
        self.start_datetime = None

    def parse(self):
        with open(self.filename, 'r') as f:
            for i, line in enumerate(f):
                if i == 0:
                    if line.split(',')[1] != 'scans':
                        raise ValueError("Invalid - Try Another CSV")
                if i == 1:  # Row 2 contains the header row location
                    self.header_row_number = int(line.split(',')[1]) + 1
                if i == 2:  # Row 3 contains date and time info
                    second_row = line.split(',')
                    self.start_datetime = pd.to_datetime(
                        second_row[1] + ' ' + second_row[3])
                    break

        # Read the CSV with the specified header
        mdf = pd.read_csv(
            self.filename, header=self.header_row_number, encoding='unicode_escape')

        # Use ms column to calculate datetime. Set as dataframe index
        mdf['Datetime'] = self.start_datetime + \
            pd.to_timedelta(mdf['ms'], unit='ms')
        mdf = mdf.set_index('Datetime')

        # Tweak columns and generate a list of compounds
        mdf = mdf.drop(['Time', 'ms'], axis=1)
        compound_list = list(mdf.columns)

        return mdf, compound_list


class BackendParser:
    def __init__(self, mdf, start_datetime, duration):
        self.mdf = mdf
        self.start_datetime = start_datetime
        self.duration = duration

    def parse(self):
        if self.start_datetime == 'Start Date: ':
            raise ValueError('Please select valid QMS file first')
        else:
            folder_path = QFileDialog.getExistingDirectory(
                None,"Select Folder","")
            if folder_path:
                # bdf, reactor_parameters, df, cycle_times_df, cycle_numbers
                # Select backend files corresponding to the dates in the selected mass spec file
                dates_to_pull = np.unique(self.mdf.index.date)
                dates_to_pull = np.insert(dates_to_pull,0,
                                            dates_to_pull.min() - pd.Timedelta(days=1))
                backend_filenames = \
                [f"data_{date.strftime('%Y-%m-%d')}.csv" for date in dates_to_pull]

                # Concatenate all requisite files and clean columns
                try:
                    backend_dataframes = \
                        [pd.read_csv(os.path.join(folder_path,f)) for f in backend_filenames]
                except FileNotFoundError as e:
                    raise ValueError('Matching CSV Not Found')
                bdf = pd.concat(backend_dataframes)
                bdf['Datetime'] = \
                    pd.to_datetime(bdf['Timestamp'], format="%m/%d/%Y %I:%M:%S %p")
                bdf = bdf.set_index('Datetime')

                bdf = bdf.drop(['Timestamp','MFC1.ID','MFC2.ID','MFC3.ID','MFC4.ID','MFC5.ID']
                                , axis=1)

                # MFC's are a little buggy. MFC2 currently going NaN during sorption swap
                bdf['MFC1.Massflow'] = bdf['MFC1.Massflow'].fillna(0)
                bdf['MFC2.Massflow'] = bdf['MFC2.Massflow'].fillna(0)
                bdf['MFC3.Massflow'] = bdf['MFC3.Massflow'].fillna(0)
                bdf['MFC4.Massflow'] = bdf['MFC4.Massflow'].fillna(0)

                # Generate a list of parameters
                reactor_parameters = list(bdf.columns)

                # Merges backend data (~5 seconds) to mass-spec points (~30 seconds)
                # Correlation tolerance is 10 seconds
                df = pd.merge_asof(self.mdf.sort_index(), bdf.sort_index(), on='Datetime',
                                    direction='nearest', tolerance=pd.Timedelta(seconds=10))
                df = df.set_index('Datetime')

                # Create a df that deals with cycle-specific values
                # Get unique cycle numbers
                cycle_numbers = df['No Completed Cycles'].dropna().unique()

                cycle_times = []
                for cycle_number in cycle_numbers:
                    # Filter the DataFrame for the current cycle number
                    cycle_data = df[df['No Completed Cycles'] == cycle_number]

                    # Get the start and end times for the current cycle
                    start_time = cycle_data.index.min()
                    end_time = cycle_data.index.max()
                    cycle_times.append({'Cycle': cycle_number,
                                        'Start': start_time, 'End': end_time})

                # Convert the list of dictionaries to a DataFrame
                cycle_times_df = pd.DataFrame(cycle_times)
                return df, reactor_parameters, cycle_times_df, cycle_times


class dataViewer(QMainWindow):
    def __init__(self, df, parameters, compounds, other):
        super().__init__()
        self.setWindowTitle("Data Viewer")
        self.setGeometry(400, 0, 800, 800)

    def something_else(self):
        return


class MyApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mitico Data Analysis")
        self.setGeometry(0, 0, 300, 2000)
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
        self.baldy2_button = QPushButton("Baldy2: Load Temp Data")
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

        run_parameters_groupbox = QGroupBox("Run Parameters")
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

        run_parameters_groupbox.setLayout(run_parameters_layout)
        main_layout.addWidget(run_parameters_groupbox)

        # RUN ANALYSIS SECTION
        self.viewer_button = QPushButton("Launch Viewer")
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
        # self.viewer_button.clicked.connect(self.launch_viewer)
        # self.capacity_button.clicked.connect(self.run_capacity_analysis)
        # self.kinetics_button.clicked.connect(self.run_kinetics_analysis)
        # self.save_csv_button.clicked.connect(self.save_csv)
        # self.save_images_button.clicked.connect(self.save_plots)
        # self.save_pdf_button.clicked.connect(self.save_pdf_report)
        # self.restart_button.clicked.connect(self.restart_analysis)

        # OTHER VARIABLES
        self.mdf = []
        self.compound_list = []

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
            except ValueError as e:
                self.file_label.setStyleSheet("color: red")
                self.file_label.setText(f"File: {e}")

    def load_reactor_data(self):
        try:
            backend_parser = BackendParser(
                self.mdf, self.time_label.text(), self.duration_label.text())
            self.mdf, reactor_parameters, cycle_times_df, cycle_times = backend_parser.parse()
            self.secondary_status.setStyleSheet("color: white")
            self.secondary_status.setText(f'Status: Reactor data merged')
            self.baldy2_button.setEnabled(False)
            self.baldy2_button.setStyleSheet("color: grey")
            print(reactor_parameters)
        except ValueError as e:
            self.secondary_status.setStyleSheet("color: red")
            self.secondary_status.setText(f'Status: {e}')


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MyApp()
    window.show()
    sys.exit(app.exec_())

from PyQt5.QtWidgets import QMainWindow, QWidget, QListWidget, QListWidgetItem, QVBoxLayout, QHBoxLayout, QLabel, QApplication, QSizePolicy
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math
import os
import csv

class CapacityAnalysis(QMainWindow):
    def __init__(self, df, cycle_times_df, file_name):
        super().__init__()

        self.df = df
        self.cycle_times_df = cycle_times_df
        self.cycle_numbers = df['No Completed Cycles'].dropna().unique()
        self.load_run_parameters(file_name)

        self.setWindowTitle("Capacity Analysis")
        screen_geometry = QApplication.desktop().screenGeometry()
        self.setGeometry(300, 0, screen_geometry.width() - 300, screen_geometry.height())
        self.setWindowFlags(self.windowFlags() | Qt.Window)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Left side: two independent matplotlib panels stacked vertically
        plot_panel = QVBoxLayout()

        # Top plot (Cycle Absorptions)
        self.figure1 = Figure(figsize=(12, 4))
        self.canvas1 = FigureCanvas(self.figure1)
        self.toolbar1 = NavigationToolbar(self.canvas1, self)
        plot_panel.addWidget(self.toolbar1)
        plot_panel.addWidget(self.canvas1)

        # Bottom plot (Sorption Metrics)
        self.figure2 = Figure(figsize=(12, 4))
        self.canvas2 = FigureCanvas(self.figure2)
        self.toolbar2 = NavigationToolbar(self.canvas2, self)
        plot_panel.addWidget(self.toolbar2)
        plot_panel.addWidget(self.canvas2)

        main_layout.addLayout(plot_panel, stretch=4)

        # Right side: controls
        control_panel = QVBoxLayout()

        self.cycle_list = QListWidget()
        self.cycle_list.setSelectionMode(QListWidget.MultiSelection)
        self.cycle_list.addItems([str(int(c)) for c in self.cycle_numbers])
        control_panel.addWidget(QLabel("Cycle Numbers to Plot"))
        control_panel.addWidget(self.cycle_list)

        self.param_list = QListWidget()
        self.param_list.setSelectionMode(QListWidget.MultiSelection)
        selectable_cols = [
            'Experimental CO2absorbed [g]',
            'Experimental CO2desorbed [g]',
            'Experimental CO2absorbed Cut [g]',
            'Sorbent Capacity [gCO2/gSorbent]',
            'Sorbent Capacity [gCO2/mLReactor]',
            'Capacity % to KPI'
        ]
        self.param_list.addItems(selectable_cols)
        for i in range(self.param_list.count()):
            self.param_list.item(i).setSelected(True)
        control_panel.addWidget(QLabel("Sorption/Desorption Metrics"))
        control_panel.addWidget(self.param_list)

        main_layout.addLayout(control_panel, stretch=1)

        self.cycle_list.itemSelectionChanged.connect(self.update_plots)
        self.param_list.itemSelectionChanged.connect(self.update_plots)

        self.perform_analysis()

    def load_run_parameters(self, file_name):
        csv_file = "run_parameters.csv"
        with open(csv_file, mode="r") as file:
            reader = csv.DictReader(file)
            last_row = None
            for row in reader:
                if row["Filename"] == file_name:
                    last_row = row

        if last_row:
            self.sorbent_mass = float(last_row["Sorbent Mass (g)"])
            self.reactor_diameter_in = float(last_row["Reactor Diameter (in)"])
            self.sorbent_bulk_density = float(last_row["Sorbent Bulk Density (g/mL)"])
            self.packing_factor = float(last_row["Packing Factor"])
            self.co2_ratio_input = float(last_row["QMS Input Ratio (baseline)"])
            self.mass_spec_co2_ratio = 0.145
            self.sorption_start_threshold = 0.1
            self.sorption_end_threshold = 0.5
        else:
            raise ValueError(f"No run parameters found for {file_name}")

    def perform_analysis(self):
        self.calculate_sorption()
        self.update_plots()

    def calculate_sorption(self):
        df = self.df
        cycle_times_df = self.cycle_times_df
        co2_molar_mass = 44.01
        sorbent_vol = self.sorbent_mass / self.sorbent_bulk_density
        start_times = []
        end_times = []
        min_gammas = []
        total_raw = []
        total_cut = []
        total_des = []

        for n in self.cycle_numbers:
            f = df[(df['Cycle Identifier'] == 3) & (df['No Completed Cycles'] == n)]
            min_y = f['yCO2'].min()
            t_start = f[f['yCO2'] < self.co2_ratio_input * self.sorption_start_threshold].index.min()
            t_end = f[(f['yCO2'] > self.co2_ratio_input * self.sorption_end_threshold) & (f.index > t_start)].index.min()
            f_cut = f[(f.index >= t_start) & (f.index <= t_end)]
            start_times.append(t_start)
            end_times.append(t_end)
            min_gammas.append(min_y)
            total_raw.append(np.sum(f['CO2absorbed[mol]']))
            total_cut.append(np.sum(f_cut['CO2absorbed[mol]']))
            d = df[(df['Cycle Identifier'] == 4) & (df['No Completed Cycles'] == n)]
            total_des.append(-np.sum(d['CO2absorbed[mol]']))

        cycle_times_df['Sorption Integration Start'] = start_times
        cycle_times_df['Sorption Integration End'] = end_times
        cycle_times_df['Highest Sorption Point'] = min_gammas
        cycle_times_df['Sorption Duration'] = np.subtract(end_times, start_times)
        cycle_times_df['Experimental CO2absorbed [mol]'] = total_raw
        cycle_times_df['Experimental CO2desorbed [mol]'] = total_des
        cycle_times_df['Experimental CO2absorbed Cut [mol]'] = total_cut
        cycle_times_df['Experimental CO2absorbed Cut [g]'] = cycle_times_df['Experimental CO2absorbed Cut [mol]'] * co2_molar_mass
        cycle_times_df['Experimental CO2absorbed [g]'] = cycle_times_df['Experimental CO2absorbed [mol]'] * co2_molar_mass
        cycle_times_df['Experimental CO2desorbed [g]'] = cycle_times_df['Experimental CO2desorbed [mol]'] * co2_molar_mass
        cycle_times_df['Sorbent Capacity [gCO2/gSorbent]'] = cycle_times_df['Experimental CO2absorbed [g]'] / self.sorbent_mass
        cycle_times_df['Sorbent Capacity [gCO2/mLReactor]'] = cycle_times_df['Experimental CO2absorbed [g]'] / sorbent_vol
        cycle_times_df['Capacity % to KPI'] = cycle_times_df['Sorbent Capacity [gCO2/mLReactor]'] / 0.0283

    def update_plots(self):
        self.figure1.clear()
        ax1 = self.figure1.add_subplot(111)

        selected_cycles = [int(i.text()) for i in self.cycle_list.selectedItems()]
        for n in selected_cycles:
            f = self.df[self.df['No Completed Cycles'] == n]
            ax1.plot((f.index - f.index[0]).total_seconds()/60, f['yCO2'], label=f"Cycle {n}")

        ax1.set_title("Cycle Absorptions")
        ax1.set_xlabel("Time (min)")
        ax1.set_ylabel("yCO2")
        ax1.legend()
        ax1.grid(True)
        self.figure1.tight_layout()
        self.canvas1.draw()

        self.figure2.clear()
        ax2 = self.figure2.add_subplot(111)
        selected_metrics = [i.text() for i in self.param_list.selectedItems()]
        for metric in selected_metrics:
            if metric in self.cycle_times_df:
                ax2.plot(self.cycle_times_df['Cycle'], self.cycle_times_df[metric], label=metric)

        ax2.set_title("Sorption & Desorption Metrics")
        ax2.set_xlabel("Cycle")
        ax2.legend()
        ax2.grid(True)
        self.figure2.tight_layout()
        self.canvas2.draw()

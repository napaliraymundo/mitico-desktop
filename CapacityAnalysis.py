from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QApplication, QPushButton, QGroupBox, QLineEdit, QListWidget
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import linregress

class CapacityAnalysis(QMainWindow):
    def __init__(self, analysis):
        self.analysis = analysis
        self.df = self.analysis.mdf
        self.cycle_times_df = self.analysis.cycle_times_df
        super().__init__()
        self.setWindowTitle("Graph Cycle")
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

        # Bottom plot (Accumulated CO2 Absorbed)
        self.figure2 = Figure(figsize=(12, 3))
        self.canvas2 = FigureCanvas(self.figure2)
        self.toolbar2 = NavigationToolbar(self.canvas2, self)
        plot_panel.addWidget(self.toolbar2)
        plot_panel.addWidget(self.canvas2)

        main_layout.addLayout(plot_panel, stretch=4)

        # Right side: controls
        control_panel = QVBoxLayout()
        control_panel.setAlignment(Qt.AlignTop)

        # Cycle Number GroupBox with selector and overrides
        cycle_groupbox = QGroupBox("Cycle Number")
        cycle_groupbox.setMinimumWidth(260)  # Make groupbox visually wider
        cycle_groupbox_layout = QVBoxLayout()
        cycle_groupbox_layout.setSpacing(8)
        cycle_groupbox_layout.setContentsMargins(8, 8, 8, 8)

        # Selector row (arrows + label)
        cycle_selector_layout = QHBoxLayout()
        self.current_cycle_index = 0
        self.left_arrow = QPushButton("←")
        self.right_arrow = QPushButton("→")
        self.cycle_label = QLabel('')
        self.left_arrow.clicked.connect(self.select_prev_cycle)
        self.right_arrow.clicked.connect(self.select_next_cycle)
        cycle_selector_layout.addWidget(self.left_arrow)
        cycle_selector_layout.addWidget(self.cycle_label)
        cycle_selector_layout.addWidget(self.right_arrow)
        cycle_selector_layout.addStretch()
        cycle_groupbox_layout.addLayout(cycle_selector_layout)

        # Sorption Start Override row (label + input)
        sorption_start_layout = QHBoxLayout()
        sorption_start_label = QLabel("Sorption Start Cut:")
        self.sorption_start_override = QLineEdit()
        self.sorption_start_override.setFixedWidth(80)
        sorption_start_layout.addWidget(sorption_start_label)
        sorption_start_layout.addWidget(self.sorption_start_override)
        sorption_start_layout.addStretch()
        cycle_groupbox_layout.addLayout(sorption_start_layout)
        self.sorption_start_override.editingFinished.connect(self.cut_start)

        # Sorption End Override row (label + input)
        sorption_end_layout = QHBoxLayout()
        sorption_end_label = QLabel("Sorption End Cut:")
        self.sorption_end_override = QLineEdit()
        self.sorption_end_override.setFixedWidth(80)
        sorption_end_layout.addWidget(sorption_end_label)
        sorption_end_layout.addWidget(self.sorption_end_override)
        sorption_end_layout.addStretch()
        cycle_groupbox_layout.addLayout(sorption_end_layout)
        self.sorption_end_override.editingFinished.connect(self.cut_end)

        cycle_groupbox.setLayout(cycle_groupbox_layout)
        control_panel.addWidget(cycle_groupbox)
        
        # Add selector for ax1 plot elements
        self.ax1_param_list = QListWidget()
        self.ax1_param_list.setSelectionMode(QListWidget.MultiSelection)
        # List of available ax1 elements
        self.ax1_elements = [
            ('yCO2', 'yCO2'),
            ('[CO2]', '[CO2]'),
            ('ln[CO2]', 'ln[CO2]'),
            ('Residence Time [s]', 'Residence Time [s]'),
        ]
        for label, col in self.ax1_elements:
            self.ax1_param_list.addItem(label)
        # Select all items by default
        for i in range(self.ax1_param_list.count()):
            self.ax1_param_list.item(i).setSelected(True)
        # Add to right control panel
        control_panel.addWidget(QLabel("Cycle Plot Elements"))
        control_panel.addWidget(self.ax1_param_list)
        self.ax1_param_list.itemSelectionChanged.connect(self.update_plots)

        main_layout.addLayout(control_panel, stretch=0)
        
    #Button functions to trim start of calculation
    def cut_start(self):
        try:
            if self.sorption_start_override.text() == '':
                self.cycle_times_df['sorption_start_cut'][self.current_cycle_index] = \
                    self.cycle_times_df['Start'][self.current_cycle_index]
            elif float(self.sorption_start_override.text()):
                self.cycle_times_df['sorption_start_cut'][self.current_cycle_index] = \
                    self.cycle_times_df['Start'][self.current_cycle_index]+ \
                        pd.to_timedelta(float(self.sorption_start_override.text()),unit='m')
                self.analysis.update_all_calculations()
        except ValueError:
            pass
    #Button function to trim end of calculation
    def cut_end(self):
        try:
            if self.sorption_end_override.text() == '':
                self.cycle_times_df['sorption_end_cut'][self.current_cycle_index] = \
                    self.cycle_times_df['Start'][self.current_cycle_index]
            elif float(self.sorption_end_override.text()):
                self.cycle_times_df['sorption_end_cut'][self.current_cycle_index] = \
                    self.cycle_times_df['Start'][self.current_cycle_index] + \
                        pd.to_timedelta(float(self.sorption_end_override.text()),unit='m')
                self.analysis.update_all_calculations()
        except ValueError:
            pass
    #Button function to view previous cycle
    def select_prev_cycle(self):
        if self.current_cycle_index > 0:
            self.current_cycle_index -= 1
            self.cycle_label.setText(f'{self.cycle_numbers[self.current_cycle_index]}/{max(self.cycle_numbers)}')
            self.sorption_start_override.clear()
            self.sorption_end_override.clear()
            self.update_plots()
    #Button function to view next cycle
    def select_next_cycle(self):
        if self.current_cycle_index < len(self.cycle_numbers) - 1:
            self.current_cycle_index += 1
            self.cycle_label.setText(f'{self.cycle_numbers[self.current_cycle_index]}/{max(self.cycle_numbers)}')
            self.sorption_start_override.clear()
            self.sorption_end_override.clear()
            self.update_plots()
    #Reload graphs on parameter or input change
    def update_plots(self):
        #Setup
        self.df = self.analysis.mdf
        self.cycle_times_df = self.analysis.cycle_times_df

        #Plot 1
        self.figure1.clear()
        ax1 = self.figure1.add_subplot(111)
        n = self.cycle_numbers[self.current_cycle_index]
        start_cut = self.cycle_times_df['sorption_start_cut'][n-1]
        end_cut = self.cycle_times_df['sorption_end_cut'][n-1]
        if 'No Completed Cycles' in self.df.columns:
            f = self.df[self.df['No Completed Cycles'] == n]
        else:
            f = self.df
        f_cut_left = f[(f.index <= start_cut)]
        f_cut_right = f[(f.index >= end_cut)]
        f_center = f[(f.index > start_cut) & (f.index < end_cut)]

        # Get selected ax1 elements
        selected_labels = [item.text() for item in self.ax1_param_list.selectedItems()]
        for label, col in self.ax1_elements:
            if label in selected_labels and col in f_center.columns:
                ax1.plot((f_center.index - f.index[0]).total_seconds()/60, f_center[col], label=label)
                # Optionally plot cut regions for yCO2 only
                if col == 'yCO2':
                    ax1.plot((f_cut_left.index - f.index[0]).total_seconds()/60, f_cut_left[col], color='grey', linestyle=':')
                    ax1.plot((f_cut_right.index - f.index[0]).total_seconds()/60, f_cut_right[col], color='grey', linestyle=':')
        
        regression_start_rel = (self.cycle_times_df['Sorption Integration Start'][n-1]-f.index[0]).total_seconds()/60
        regression_end_rel = (self.cycle_times_df['Sorption Integration End'][n-1]-f.index[0]).total_seconds()/60
        sorption_start_rel = (f_center.index[0] - f.index[0]).total_seconds()/60
        sorption_end_rel = (f_center.index[-1] - f.index[0]).total_seconds()/60
        # Get colors from plotted lines for yCO2 and Residence Time [s]
        yco2_color = None
        residence_time_color = None
        for line in ax1.get_lines():
            label = line.get_label()
            if label == 'yCO2': yco2_color = line.get_color()
            elif label == 'Residence Time [s]': residence_time_color = line.get_color()
        # Fallback to default colors if not found
        if yco2_color is None:
            yco2_color = 'blue'
        if residence_time_color is None:
            residence_time_color = 'red'

        ax1.axvline(x=regression_start_rel, linestyle='--',
                label=f'Regression Start = {self.analysis.sorption_start_input.text()}%',
                color=residence_time_color)
        ax1.axvline(x=regression_end_rel, linestyle='--',
                label=f'Regression End = {self.analysis.sorption_end_input.text()}%',
                color=residence_time_color)
        ax1.axvline(x=sorption_start_rel, linestyle='--',
                label=f'Sorption Start = {int(sorption_start_rel)}min',
                color=yco2_color)
        ax1.axvline(x=int(sorption_end_rel), linestyle='--',
                label=f'Sorption End = {int(sorption_end_rel)}min',
                color=yco2_color)
        ax1.set_title(f'Cycle #{n} Absorption Plot')
        ax1.set_xlabel("Time (min)")
        ax1.legend()
        ax1.grid(True)
        self.figure1.tight_layout()
        self.canvas1.draw()

        # Bottom plot: Accumulated CO2 Absorbed for selected cycle
        self.figure2.clear()
        ax2 = self.figure2.add_subplot(111)
        # Retrim
        start_cut = self.cycle_times_df['Sorption Integration Start'][n-1]
        end_cut = self.cycle_times_df['Sorption Integration End'][n-1]
        f_center = f[(f.index > start_cut) & (f.index < end_cut)]
        if 'Accumulated CO2 Absorbed [mol]' in f.columns:
            ax2.plot(f_center['Residence Time [s]'], f_center['ln[CO2]'], label=f'Cycle #{n}')
            # Plot the fitted line from cycle_times_df
            k = self.cycle_times_df['rate_constant_k'][n-1]
            # lnco2_t0 = self.cycle_times_df['lnCO2_t0'][n-1]
            r2 = self.cycle_times_df['regression_r2'][n-1] if 'regression_r2' in self.cycle_times_df.columns else None
            if np.isfinite(k): #and np.isfinite(lnco2_t0):
                x_fit = f_center['Residence Time [s]'].values
                y_fit = (-k * x_fit) +  self.constant_lnco2_0 #lnco2_t0  # Correct sign for -k
                label = f"Fit: ln[CO2] = -{k:.3f}·t + {self.constant_lnco2_0:.3f} (R² = {r2:.3f})" if r2 is not None and np.isfinite(r2) else "Fit: ln[CO2] = -k·t + ln[CO2]_0"
                ax2.plot(x_fit, y_fit, '--', color='red', label=label)
            ax2.set_xlabel("Residence Time [s]")
            ax2.set_title(f'Cycle #{n} Kinetics Regression')
            ax2.set_ylabel("ln[CO2]")
            ax2.legend()
            ax2.grid(True)
        self.figure2.tight_layout()
        self.canvas2.draw()

    #Calculate variables which only depend on df
    def calculate_secondary(self):
        self.df = self.analysis.mdf
        self.cycle_times_df = self.analysis.cycle_times_df
        self.cycle_numbers = self.cycle_times_df['Cycle'].tolist()
        self.cycle_label.setText(f'{self.cycle_numbers[self.current_cycle_index]}/{max(self.cycle_numbers)}')

        self.df['TimeDiff'] = self.df.index.diff()
        reactor_pressure = 101325 #Pa
        gas_constant_r = 8.3145
        reactor_temp_c = 55
        reactor_temp_k = reactor_temp_c + 273.15
        sccm_to_molar = reactor_pressure * (1e-6) / (60) / gas_constant_r / 273.15

        ref_gas = self.analysis.reference_gas_dropdown.currentText()
        gas_abbr = self.analysis.gas_abbr  # Use the lookup from analysis
        abbr = gas_abbr.get(ref_gas, ref_gas)
        if ref_gas in self.df.columns:
            self.df['CO2 / ' + abbr] = self.df['Carbon dioxide'] / self.df[ref_gas]
            co2_ref_col = 'CO2 / ' + abbr
        else:
            # fallback to Nitrogen if not found
            self.df['CO2 / N2'] = self.df['Carbon dioxide'] / self.df['Nitrogen']
            co2_ref_col = 'CO2 / N2'

        correction = float(self.analysis.reactor_input_ratio)/float(self.analysis.qms_input_ratio)  
        self.df['yCO2'] = self.df[co2_ref_col] * correction
        input_flow_rate_sccm = float(self.analysis.input_flow_rate)
        input_flow_rate_molar = input_flow_rate_sccm * sccm_to_molar
        co2_input_flow_rate_molar = input_flow_rate_molar * float(self.analysis.reactor_input_ratio) / 100 #since the input is a %
        self.df['[CO2]']=self.df['yCO2']*reactor_pressure/gas_constant_r/reactor_temp_k
        self.df['ln[CO2]'] = np.log(self.df['[CO2]'])
        self.df['CO2 Partial Flow Rate Out [mol/s]'] = self.df['yCO2']* input_flow_rate_molar
        self.df['CO2 Absorbed [mol]'] = (co2_input_flow_rate_molar - \
           self.df['CO2 Partial Flow Rate Out [mol/s]']) * self.df['TimeDiff'].dt.total_seconds()
        
        self.analysis.mdf = self.df
        self.analysis.cycle_times_df = self.cycle_times_df
        for param in [co2_ref_col, 'yCO2', '[CO2]', 'ln[CO2]', 'CO2 Partial Flow Rate Out [mol/s]', 'CO2 Absorbed [mol]']:
            if param not in self.analysis.other_parameters:
                self.analysis.other_parameters.append(param)
        self.analysis.viewer_instance.update_plot()
        return

    #Calculate variables which rely on df and cycle_times_df
    def calculate_sorption(self):
        self.df = self.analysis.mdf
        self.cycle_times_df = self.analysis.cycle_times_df
        # Initialize columns to empty if they don't exist
        if 'sorption_start_cut' not in self.cycle_times_df.columns:
            self.cycle_times_df['sorption_start_cut'] = self.cycle_times_df['Start']
        if 'sorption_end_cut' not in self.cycle_times_df.columns:
            self.cycle_times_df['sorption_end_cut'] = self.cycle_times_df['End']

        co2_molar_mass = 44.01
        sorbent_vol = float(self.analysis.sorbent_mass_input.text()) / float(self.analysis.bulk_density_input.text())
        start_times = []
        end_times = []
        min_gammas = []
        total_absorbed = []
        sorbent_mass = float(self.analysis.sorbent_mass_input.text())
        sorption_start_threshold = float(self.analysis.sorption_start_input.text())/100
        sorption_end_threshold = float(self.analysis.sorption_end_input.text())/100

        for n in self.cycle_numbers:
            #Prep data frame
            f = self.df
            if 'Cycle Identifier' in self.df.columns:
                f = self.df[(self.df['Cycle Identifier'] == 3) & (self.df['No Completed Cycles'] == n)]
            #Cut the single cycle dataframe based on sorption_start/end_cut
            start_cut = self.cycle_times_df['sorption_start_cut'][n-1]
            end_cut = self.cycle_times_df['sorption_end_cut'][n-1]
            f = f[(f.index > start_cut) & (f.index < end_cut)]
            
            t_start = f[f['yCO2'] > sorption_start_threshold].index.min()
            t_end = f[(f['yCO2'] > sorption_end_threshold) & (f.index > t_start)].index.min()
            f_cut = f[(f.index >= t_start) & (f.index <= t_end)]
            min_y = f_cut['yCO2'].min()
            total_absorbed.append(np.sum(f['CO2 Absorbed [mol]']))
            start_times.append(t_start)
            end_times.append(t_end)
            min_gammas.append(min_y)

        self.cycle_times_df['Sorption Integration Start'] = start_times
        self.cycle_times_df['Sorption Integration End'] = end_times
        self.cycle_times_df['Highest Sorption Point'] = min_gammas
        self.cycle_times_df['Sorption Duration'] = np.subtract(end_cut, start_cut)
        self.cycle_times_df['Experimental CO2absorbed [mol]'] = total_absorbed
        self.cycle_times_df['Experimental CO2absorbed [g]'] = self.cycle_times_df['Experimental CO2absorbed [mol]'] * co2_molar_mass
        self.cycle_times_df['Sorbent Capacity [gCO2/gSorbent]'] = self.cycle_times_df['Experimental CO2absorbed [g]'] / sorbent_mass
        self.cycle_times_df['Sorbent Capacity [gCO2/mLReactor]'] = self.cycle_times_df['Experimental CO2absorbed [g]'] / sorbent_vol
        self.cycle_times_df['Capacity % to KPI'] = self.cycle_times_df['Sorbent Capacity [gCO2/mLReactor]'] / 0.0283

    #Calculate variables which rely on sorption integration start and end
    def calculate_kinetics(self):
        self.df = self.analysis.mdf
        self.cycle_times_df = self.analysis.cycle_times_df
        df = self.df
        df['Accumulated CO2 Absorbed [mol]'] = np.nan
        df['Volume of Active Sorbent [mL]'] = np.nan
        df['Residence Time [s]'] = np.nan
        co2_molar_mass = 44.01
        self.constant_lnco2_0 = 1.312488772
        sorbent_vol = float(self.analysis.sorbent_mass_input.text()) / float(self.analysis.bulk_density_input.text())
        # Prepare lists for regression results
        rate_constants = []
        lnco2_t0s = []
        r2s = []
        for idx, n in enumerate(self.cycle_numbers):
            cycle_times_df = self.cycle_times_df
            if 'No Completed Cycles' in df.columns:
                f = df[df['No Completed Cycles'] == n]
            else:
                f = df
            #Masking from beginning of sorption to end of integration
            start_time = cycle_times_df['sorption_start_cut'][n-1]
            end_time = cycle_times_df['Sorption Integration End'][n-1]

            mask = (f.index >= start_time) & (f.index <= end_time)
            # Compute cumulative sum for the masked slice
            absorbed_cumsum = f.loc[mask, 'CO2 Absorbed [mol]'].cumsum()
            sorbent_active_volume = sorbent_vol - (absorbed_cumsum * co2_molar_mass \
                                                   / cycle_times_df['Sorbent Capacity [gCO2/mLReactor]'][n-1])
            residence_time = sorbent_active_volume / float(self.analysis.input_flow_rate) * 60
            # Insert the cumulative sum into the main df for the same indices
            df.loc[f.loc[mask].index, 'Accumulated CO2 Absorbed [mol]'] = absorbed_cumsum
            df.loc[f.loc[mask].index, 'Volume of Active Sorbent [mL]'] = sorbent_active_volume
            df.loc[f.loc[mask].index, 'Residence Time [s]'] = residence_time

            # Further trim the area to within the regression region
            start_time = cycle_times_df['Sorption Integration Start'][n-1]
            end_time = cycle_times_df['Sorption Integration End'][n-1]

            f = f[(f.index > start_time) & (f.index < end_time)]
            # Linear regression: ln[CO2] = -k*t + intercept
            x = residence_time[f.index].values
            y = f['ln[CO2]'].values
            if len(x) > 1:
                # Force fit with constant y-intercept (constant_lnco2_0)
                # y = -k * x + constant_lnco2_0 => y - constant_lnco2_0 = -k * x
                y_adj = y - self.constant_lnco2_0
                # Fit slope only
                slope, _, r_value, p_value, std_err = linregress(x, y_adj)
                rate_constant_k = -slope
                # lnCO2_t0 = constant_lnco2_0  # Forced intercept
                regression_r2 = r_value ** 2
            else:
                rate_constant_k = np.nan
                # lnCO2_t0 = np.nan
                regression_r2 = np.nan
            # Save to lists for this cycle
            rate_constants.append(rate_constant_k)
            # lnco2_t0s.append(lnCO2_t0)
            r2s.append(regression_r2)
        # Save to cycle_times_df for all cycles
        self.cycle_times_df['rate_constant_k'] = rate_constants
        # self.cycle_times_df['lnCO2_t0'] = lnco2_t0s
        self.cycle_times_df['regression_r2'] = r2s
        return

    def setup_metric_selector(self):
        self.metric_selector.clear()
        for metric in self.metrics:
            self.metric_selector.addItem(metric)
        # Select all metrics by default
        for i in range(self.metric_selector.count()):
            self.metric_selector.item(i).setSelected(True)
    
    def get_all_figures_for_pdf(self):
        """Return a list of matplotlib Figure objects for all cycles (both ax1 and ax2 plots)."""
        figures = []
        # Save current state
        orig_cycle_index = self.current_cycle_index
        n_cycles = len(self.cycle_numbers)
        for idx in range(n_cycles):
            self.current_cycle_index = idx
            self.update_plots()  # Ensure plots are updated for this cycle
            # Deepcopy figures to avoid reference issues
            import copy
            fig1 = copy.deepcopy(self.figure1)
            fig2 = copy.deepcopy(self.figure2)
            figures.append(fig1)
            figures.append(fig2)
        # Restore original state
        self.current_cycle_index = orig_cycle_index
        self.update_plots()
        return figures
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, \
    QApplication, QPushButton, QGroupBox, QLineEdit, QListWidget
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import pandas as pd
from numpy import nan, sum, maximum, isfinite, pi, e, log, subtract, number, floor, \
    log10
from scipy.stats import linregress
import ast

class CapacityAnalysis(QMainWindow):
    def __init__(self, analysis):
        super().__init__()

        self.analysis = analysis
        self.df = self.analysis.mdf
        self.cycle_times_df = self.analysis.cycle_times_df
        self.xlim = [None] * len(self.cycle_times_df)
        self.ylim = [None] * len(self.cycle_times_df)

        self.setWindowTitle("Graph Cycle")
        screen_geometry = QApplication.desktop().screenGeometry()
        self.setGeometry(300, 0, \
                         screen_geometry.width() - 300, screen_geometry.height())
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
        home_action = self.toolbar1.actions()[0]
        home_action.triggered.disconnect()
        home_action.triggered.connect(self.on_home_clicked)
        plot_panel.addWidget(self.toolbar1)
        plot_panel.addWidget(self.canvas1)

        # Bottom plot (Accumulated CO2 Absorbed)
        self.figure2 = Figure(figsize=(12, 3))
        self.canvas2 = FigureCanvas(self.figure2)
        # Don't need a toolbar for bottom
        # self.toolbar2 = NavigationToolbar(self.canvas2, self)
        # plot_panel.addWidget(self.toolbar2)
        plot_panel.addWidget(self.canvas2)

        main_layout.addLayout(plot_panel, stretch=4)

        # Right side: controls
        control_panel = QVBoxLayout()
        control_panel.setAlignment(Qt.AlignTop)

        # Cycle Number GroupBox with selector and overrides
        cycle_groupbox = QGroupBox("Manual Cuts")
        cycle_groupbox.setMinimumWidth(260)  # Make groupbox visually wider
        cycle_groupbox_layout = QVBoxLayout()
        cycle_groupbox_layout.setSpacing(8)
        cycle_groupbox_layout.setContentsMargins(8, 8, 8, 8)

        # Selector row (arrows + label)
        cycle_selector_layout = QHBoxLayout()
        self.current_cycle_index = 0
        self.previous_cycle_index = 0
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
        sorption_start_layout.addStretch()
        sorption_start_layout.addWidget(self.sorption_start_override)
        cycle_groupbox_layout.addLayout(sorption_start_layout)
        self.sorption_start_override.editingFinished.connect(self.cut_start)
        self.sorption_start_input_previous = ''

        # Sorption End Override row (label + input)
        sorption_end_layout = QHBoxLayout()
        sorption_end_label = QLabel("Sorption End Cut:")
        self.sorption_end_override = QLineEdit()
        self.sorption_end_override.setFixedWidth(80)
        sorption_end_layout.addWidget(sorption_end_label)
        sorption_end_layout.addStretch()
        sorption_end_layout.addWidget(self.sorption_end_override)
        cycle_groupbox_layout.addLayout(sorption_end_layout)
        self.sorption_end_override.editingFinished.connect(self.cut_end)
        self.sorption_end_input_previous = ''

        # Regression Start Override row
        regression_start_layout = QHBoxLayout()
        regression_start_label = QLabel("Regression Start Cut:")
        self.regression_start_override = QLineEdit()
        self.regression_start_override.setFixedWidth(80)
        regression_start_layout.addWidget(regression_start_label)
        regression_start_layout.addStretch()
        regression_start_layout.addWidget(self.regression_start_override)
        cycle_groupbox_layout.addLayout(regression_start_layout)
        self.regression_start_override.editingFinished.connect(\
            self.cut_regression_start)
        self.regression_start_input_previous = ''

        # Regression End Override row
        regression_end_layout = QHBoxLayout()
        regression_end_label = QLabel("Regression End Cut:")
        self.regression_end_override = QLineEdit()
        self.regression_end_override.setFixedWidth(80)
        regression_end_layout.addWidget(regression_end_label)
        regression_end_layout.addStretch()
        regression_end_layout.addWidget(self.regression_end_override)
        cycle_groupbox_layout.addLayout(regression_end_layout)
        self.regression_end_override.editingFinished.connect(\
            self.cut_regression_end)
        self.regression_end_input_previous = ''

        cycle_groupbox.setLayout(cycle_groupbox_layout)
        control_panel.addWidget(cycle_groupbox)
        
        # Add selector for ax1 plot elements
        self.ax1_param_list = QListWidget()
        self.ax1_param_list.setSelectionMode(QListWidget.MultiSelection)

        # List of available ax1 elements
        self.ax1_elements = [
            'yCO2 [%]',
            '[CO2]',
            'ln[CO2]',
            'Residence Time [s]',
        ]
        for label in self.ax1_elements:
            self.ax1_param_list.addItem(label)

        self.reactor_param_list = QListWidget()
        self.reactor_param_list.setSelectionMode(QListWidget.MultiSelection)

        # Add to right control panel
        control_panel.addWidget(QLabel("Metrics"))
        control_panel.addWidget(self.ax1_param_list)
        self.ax1_param_list.itemSelectionChanged.connect(self.update_selection)
        control_panel.addWidget(QLabel("Reactor Parameters"))
        control_panel.addWidget(self.reactor_param_list)
        self.reactor_param_list.itemSelectionChanged.connect(self.update_selection)

        # === Add Scaling Factors Checkbox ===
        self.scaling_checkbox = QPushButton("Apply Scaling Factors")
        self.scaling_checkbox.setCheckable(True)
        self.scaling_checkbox.setChecked(False)
        control_panel.addWidget(self.scaling_checkbox)
        control_panel.addStretch()
        self.scaling_checkbox.toggled.connect(self.update_selection)

        main_layout.addLayout(control_panel, stretch=0)

    ##  ---- cut_start, cut_end, cut_regression_start, cut_regression_end
    ##  Modifies self.start cuts and pushes state up + updates tab
    ##  A cleared checkbox '' removes a cut from the data
    ##  Value must castable as a float

    def cut_start(self):
        """Button functions to trim start of calculation"""
        if self.sorption_start_input_previous != self.sorption_start_override.text():
            try:
                if self.sorption_start_override.text() == '':
                    self.start_cuts[self.current_cycle_index] = None
                    self.sorption_start_input_previous = ''
                else:
                    self.sorption_start_input_previous = self.sorption_start_override.text()
                    float_val = float(self.sorption_start_override.text())
                    start = self.cycle_times_df['Start'][self.current_cycle_index]
                    end = self.cycle_times_df['End'][self.current_cycle_index]
                    cut_time = start + pd.to_timedelta(float_val, unit='m')
                    if (start < cut_time < end):
                        self.start_cuts[self.current_cycle_index] = float_val
                        self.analysis.parameter_status.setText("Status: App State Changed (unsaved)")
                    else: 
                        self.sorption_start_override.clear()
                        self.sorption_start_input_previous = ''
                self.push_state()
                self.propagate_change()
            except ValueError: #Don't update the dataframe if a nonfloat is entered
                self.sorption_start_override.clear()
                self.sorption_start_input_previous = ''
                pass

    def cut_end(self):
        """Button function to trim end of calculation"""
        if self.sorption_end_input_previous != self.sorption_end_override.text():
            try:
                if self.sorption_end_override.text() == '':
                    self.end_cuts[self.current_cycle_index] = None
                    self.sorption_end_input_previous = ''
                else:
                    self.sorption_end_input_previous = self.sorption_end_override.text()
                    float_val = float(self.sorption_end_override.text())
                    start = self.cycle_times_df['Start'][self.current_cycle_index]
                    start_cut = self.cycle_times_df['Sorption Start Time'][self.current_cycle_index]
                    start_time = start + pd.to_timedelta(start_cut, unit='m')
                    end = self.cycle_times_df['End'][self.current_cycle_index]
                    cut_time = start + pd.to_timedelta(float_val, unit='m')
                    if (start_time < cut_time < end):
                        self.end_cuts[self.current_cycle_index] = float_val
                        self.analysis.parameter_status.setText("Status: App State Changed (unsaved)")
                    else: 
                        self.sorption_end_override.clear()
                        self.sorption_end_input_previous = ''
                self.push_state()
                self.propagate_change()
            except ValueError: #Don't update the dataframe if a nonfloat is entered
                self.sorption_end_override.clear()
                self.sorption_end_input_previous = ''
                pass

    def cut_regression_start(self):
        if self.regression_start_input_previous != self.regression_start_override.text():
            try:
                if self.regression_start_override.text() == '':
                    self.regression_start_cuts[self.current_cycle_index] = None
                    self.regression_start_input_previous = ''
                else:
                    self.regression_start_input_previous = self.regression_end_override.text()
                    float_val = float(self.regression_start_override.text())
                    start = self.cycle_times_df['Start'][self.current_cycle_index]
                    start_cut = self.cycle_times_df['Sorption Start Time'][self.current_cycle_index]
                    start_time = start + pd.to_timedelta(start_cut, unit='m')
                    end_cut = self.cycle_times_df['Sorption End Time'][self.current_cycle_index]
                    end_time = start + pd.to_timedelta(end_cut, unit='m')
                    cut_time = start + pd.to_timedelta(float_val, unit='m')
                    if (start_time < cut_time < end_time):
                        self.regression_start_cuts[self.current_cycle_index] = float_val
                        self.analysis.parameter_status.setText("Status: App State Changed (unsaved)")
                    else: 
                        self.regression_start_override.clear()
                        self.regression_start_input_previous = ''
                self.push_state()
                self.propagate_change()
            except ValueError: #Don't update the dataframe if a nonfloat is entered
                self.regression_start_override.clear()
                self.regression_start_input_previous = ''
                pass

    
    def cut_regression_end(self):
        if self.regression_end_input_previous != self.regression_end_override.text():
            try:
                if self.regression_end_override.text() == '':
                    self.regression_end_cuts[self.current_cycle_index] = None
                    self.regression_end_input_previous = ''
                else:
                    self.regression_end_input_previous = self.regression_end_override.text()
                    float_val = float(self.regression_end_override.text())
                    start = self.cycle_times_df['Start'][self.current_cycle_index]
                    start_cut = self.cycle_times_df['Sorption Start Time'][self.current_cycle_index]\
                        if self.regression_start_cuts[self.current_cycle_index] is None else\
                        self.regression_start_cuts[self.current_cycle_index]
                    start_time = start + pd.to_timedelta(start_cut, unit='m')
                    end_cut = self.cycle_times_df['Sorption End Time'][self.current_cycle_index]
                    end_time = start + pd.to_timedelta(end_cut, unit='m')
                    cut_time = start + pd.to_timedelta(float_val, unit='m')
                    if (start_time < cut_time < end_time):
                        self.regression_end_cuts[self.current_cycle_index] = float_val
                        self.analysis.parameter_status.setText("Status: App State Changed (unsaved)")
                    else: 
                        self.regression_end_override.clear()
                        self.regression_end_input_previous = ''
                self.push_state()
                self.propagate_change()
            except ValueError: #Don't update the dataframe if a nonfloat is entered
                self.regression_start_override.clear()
                self.regression_start_input_previous = ''
                pass
    
    def update_selection(self):
        #Save graph state
        xlims = (tuple(float(x) for x in self.ax1.get_xlim()))
        ylims = (tuple(float(x) for x in self.ax1.get_ylim()))
        self.xlim[self.current_cycle_index] = xlims
        self.ylim[self.current_cycle_index] = ylims
        self.update_plots()

    def propagate_change(self, all=False):
        self.pull_state()
        self.calculate_sorption()
        self.calculate_kinetics_dry()
        self.calculate_kinetics_wet()
        self.update_plots()

    def pull_state(self):
        #Repopulate param lists
        self.ax1_param_list.blockSignals(True)
        self.reactor_param_list.blockSignals(True)
        self.reactor_param_list.clear()
        self.reactor_param_list.addItems(self.analysis.reactor_parameters)
        selected_parameters = self.analysis.state_qlist['Cycle Parameters']
        selected_metrics = self.analysis.state_qlist['Cycle Plot Elements']
        for i in range(self.reactor_param_list.count()):
            self.reactor_param_list.item(i).setSelected(\
                self.reactor_param_list.item(i).text() in selected_parameters)
        for i in range(self.ax1_param_list.count()):
            self.ax1_param_list.item(i).setSelected(\
                self.ax1_param_list.item(i).text() in selected_metrics)
        #Set selected in param list

        self.cycle_times_df = self.analysis.cycle_times_df
        self.df = self.analysis.mdf
        number_of_cycles = len(self.cycle_times_df)
        self.cycle_numbers = self.cycle_times_df['Cycle'].tolist()

        #Pull graph limit state
        self.xlim = self.analysis.state_other['Cycle Graph Xlim']
        self.ylim = self.analysis.state_other['Cycle Graph Ylim']

        #If the analysis state is the wrong length, reset to nones
        if len(self.xlim) != number_of_cycles:
            self.xlim = [None] * len(self.cycle_times_df)
            self.ylim = [None] * len(self.cycle_times_df)
            print('renonned because of length')

        #Secondary calculation is not dependent on cut timing
        self.calculate_secondary()

        #Arrange timing for all four cuts
        if len(self.analysis.state_other['Start Cuts']) != number_of_cycles:
            self.start_cuts = [None] * number_of_cycles
            self.end_cuts = [None] * number_of_cycles
            self.regression_start_cuts = [None] * number_of_cycles
            self.regression_end_cuts = [None] * number_of_cycles
        else:
            self.start_cuts = self.analysis.state_other['Start Cuts']
            self.end_cuts = self.analysis.state_other['End Cuts']
            self.regression_start_cuts = self.analysis.state_other['Regression Start Cuts']
            self.regression_end_cuts = self.analysis.state_other['Regression End Cuts']

        start_times = []
        end_times = []
        regression_start_times = []
        regression_end_times = []
        regression_start_percent = \
            float(self.analysis.state_text['Regression Start (%)'])
        regression_end_percent = float(self.analysis.state_text['Regression End (%)'])

        for n in self.cycle_numbers:
            n = int(n)
            start_time = self.cycle_times_df['Start'][n-1]
            end_time = self.cycle_times_df['End'][n-1]

            if self.start_cuts[n-1] is not None:
                start_cut = self.start_cuts[n-1] 
                start_cut_time = start_time + pd.to_timedelta(start_cut,unit='m')
            else: 
                start_cut = 0
                start_cut_time = start_time

            #First cut between the start cut and end of data to find regression points
            f = self.df[(self.df.index > start_cut_time) & (self.df.index < end_time)]
            if 'Cycle Identifier' in self.df.columns:
                f = f[(f['Cycle Identifier'] == 3) & \
                            (f['No Completed Cycles'] == n)]    
            regression_start_time_percent = \
                f[f['yCO2 [%]'] > regression_start_percent].index.min()
            regression_end_time_percent = \
                f[(f['yCO2 [%]'] > regression_end_percent) & \
                (f.index > regression_start_time_percent)].index.min()
            
            if self.end_cuts[n-1] is not None:
                end_cut = self.end_cuts[n-1]
            else: end_cut = ((regression_end_time_percent - start_time)\
                .total_seconds()/60)
            if self.regression_start_cuts[n-1] is not None:
                regression_start_cut = self.regression_start_cuts[n-1]
            else: regression_start_cut = min(max((regression_start_time_percent-start_time)\
                .total_seconds()/60, start_cut),end_cut)
            if self.regression_end_cuts[n-1] is not None:
                regression_end_cut = self.regression_end_cuts[n-1]
            else: regression_end_cut = min((regression_end_time_percent-start_time)\
                .total_seconds()/60, end_cut)

            start_times.append(start_cut)
            end_times.append(end_cut)
            regression_start_times.append(regression_start_cut)
            regression_end_times.append(regression_end_cut)

        self.cycle_times_df['Sorption Start Time'] = start_times 
        self.cycle_times_df['Sorption End Time'] = end_times
        self.cycle_times_df['Regression Start Time'] = regression_start_times
        self.cycle_times_df['Regression End Time'] = regression_end_times

        #Unblock signals from dropdowns
        self.ax1_param_list.blockSignals(False)
        self.reactor_param_list.blockSignals(False)

    def push_state(self):
        selected_labels = [item.text() for item in self.ax1_param_list.selectedItems()]
        selected_params = [item.text() for item in self.reactor_param_list.selectedItems()]
        self.analysis.state_qlist['Cycle Plot Elements'] = selected_labels
        self.analysis.state_qlist['Cycle Parameters'] = selected_params
        self.analysis.state_other['Start Cuts'] = self.start_cuts
        self.analysis.state_other['End Cuts'] = self.end_cuts
        self.analysis.state_other['Regression Start Cuts'] = self.regression_start_cuts
        self.analysis.state_other['Regression End Cuts'] =  self.regression_end_cuts
        self.analysis.cycle_times_df = self.cycle_times_df
        xlims = (tuple(float(x) for x in self.ax1.get_xlim()))
        ylims = (tuple(float(x) for x in self.ax1.get_ylim()))
        self.xlim[self.current_cycle_index] = xlims
        self.ylim[self.current_cycle_index] = ylims
        self.analysis.state_other['Cycle Graph Xlim'] = self.xlim
        self.analysis.state_other['Cycle Graph Ylim'] = self.ylim
        self.analysis.metrics_instance.update_table()
        self.analysis.metrics_instance.update_plot()

    #Reload graphs on parameter or input change
    def update_plots(self):
        #Populate text boxes
        start_override_text = str(\
            self.start_cuts[self.current_cycle_index])\
                  if self.start_cuts[self.current_cycle_index]\
                      is not None else ''
        self.sorption_start_override.setText(start_override_text)
        self.sorption_start_input_previous = start_override_text
        end_override_text = str(\
            self.end_cuts[self.current_cycle_index])\
                  if self.end_cuts[self.current_cycle_index]\
                      is not None else ''
        self.sorption_end_override.setText(end_override_text)
        self.sorption_end_input_previous = end_override_text
        rstart_override_text = str(\
            self.regression_start_cuts[self.current_cycle_index])\
                  if self.regression_start_cuts[self.current_cycle_index]\
                      is not None else ''
        self.regression_start_override.setText(rstart_override_text)
        self.regression_start_input_previous = rstart_override_text
        rend_override_text = str(\
            self.regression_end_cuts[self.current_cycle_index])\
                  if self.regression_end_cuts[self.current_cycle_index]\
                      is not None else ''
        self.regression_end_override.setText(rend_override_text)
        self.regression_end_input_previous = rend_override_text

        #Plot Setup
        self.figure1.clear()

        self.ax1 = self.figure1.add_subplot(111)
        n = self.cycle_numbers[self.current_cycle_index]
        start_time = self.cycle_times_df['Start'][self.current_cycle_index]
        start_cut = start_time + pd.to_timedelta(\
            self.cycle_times_df['Sorption Start Time'][n-1],unit='m')
        end_cut = start_time + pd.to_timedelta(\
            self.cycle_times_df['Sorption End Time'][n-1],unit='m')
        if 'No Completed Cycles' in self.df.columns:
            f = self.df[self.df['No Completed Cycles'] == n]
        else:
            f = self.df
        f_cut_left = f[(f.index <= start_cut)]
        f_cut_right = f[(f.index >= end_cut)]
        f_center = f[(f.index > start_cut) & (f.index < end_cut)]

        # Get selected ax1 and reactor param list elements
        selected_labels = [item.text() for item in self.ax1_param_list.selectedItems()]\
            + [item.text() for item in self.reactor_param_list.selectedItems()]

        use_scaling = self.scaling_checkbox.isChecked()
        scaling_factors = None
        #Populate scaling dict and labels
        if use_scaling and selected_labels:
            self.ax1.set_ylim(-2,12)
            scaling_factors = {}
            for label in selected_labels:
                scaling_factors[label] = self.calculate_scaling_factors(\
                    f, [label], start_cut, end_cut).get(label, 1)
        #Plot elements which are to be autoscaled
        for label in selected_labels:
            if label in f_center.columns:
                ydata = f_center[label]
                if use_scaling and scaling_factors and label in scaling_factors:
                    ydata = ydata / scaling_factors[label]
                    plot_label = f"{label} / {scaling_factors[label]:.2f}"
                else:
                    plot_label = label
                self.ax1.plot((f_center.index - f.index[0]).total_seconds()/60, ydata,\
                          label=plot_label)
        self.ax1.autoscale(axis='y')
        #Plot left and right cut elements (not to be autoscaled)
        for label in selected_labels:
            if label in f_center.columns:
                ydata_left = f_cut_left[label]
                ydata_right = f_cut_right[label]
                if use_scaling and scaling_factors and label in scaling_factors:
                    ydata_left = ydata_left / scaling_factors[label]
                    ydata_right = ydata_right / scaling_factors[label]
                self.ax1.plot((f_cut_left.index - f.index[0]).total_seconds()/60,\
                            ydata_left, color='grey', linestyle=':')
                self.ax1.plot((f_cut_right.index - f.index[0]).total_seconds()/60,\
                            ydata_right, color='grey', linestyle=':')
        
        # cut_time = start + pd.to_timedelta(float_val, unit='m')
        regression_start_rel = self.cycle_times_df['Regression Start Time'][n-1]
        regression_end_rel = self.cycle_times_df['Regression End Time'][n-1]
        sorption_start_rel = self.cycle_times_df['Sorption Start Time'][n-1]
        sorption_end_rel = self.cycle_times_df['Sorption End Time'][n-1]

        # Get colors from plotted lines for yCO2 and Residence Time [s]
        yco2_color = None
        residence_time_color = None
        for line in self.ax1.get_lines():
            label = line.get_label()
            if label == 'yCO2 [%]': yco2_color = line.get_color()
            elif label == 'Residence Time [s]': residence_time_color = line.get_color()
        # Fallback to default colors if not found
        if yco2_color is None:
            yco2_color = 'blue'
        if residence_time_color is None:
            residence_time_color = 'red'

        #Draw vertical lines
        self.ax1.axvline(x=sorption_start_rel,
            label=f'Sorption Start = {sorption_start_rel:.1f}min',
            color=yco2_color)
        if float(sorption_end_rel): self.ax1.axvline(x=sorption_end_rel,
            label=f'Sorption End = {sorption_end_rel:.1f}min',
            color=yco2_color)
        if float(regression_start_rel):\
            self.ax1.axvline(x=regression_start_rel, linestyle=(0,(5,10)),
            label=f"Regression Start = {self.analysis.state_text['Regression Start (%)']}%"\
            if self.regression_start_cuts[self.current_cycle_index] is None else \
            f"Regression Start = {regression_start_rel:.1f}min",
            color=residence_time_color)
        if float(regression_end_rel):\
            self.ax1.axvline(x=regression_end_rel, linestyle=(0,(5,10)),
            label=f"Regression End = {self.analysis.state_text['Regression End (%)']}%"\
            if self.regression_end_cuts[self.current_cycle_index] is None else \
            f"Regression End = {regression_end_rel:.1f}min",
            color=residence_time_color)
        
        
        #Config labels and legend
        self.ax1.set_title(f'Cycle #{n} Absorption Plot')
        self.ax1.set_xlabel("Time (min)")
        self.ax1.legend()
        self.ax1.grid(True)
        self.figure1.tight_layout(pad=1)
        self.canvas1.draw()

        #Scaling config for plot 1
        if self.xlim[self.current_cycle_index] is not None:
            self.ax1.set_xlim(self.xlim[self.current_cycle_index])
            self.ax1.set_ylim(self.ylim[self.current_cycle_index])
            print('loaded state ', self.xlim[self.current_cycle_index])
        self.canvas1.draw()

        #
        # Bottom plot: Accumulated CO2 Absorbed for selected cycle
        #

        self.figure2.clear()
        ax2 = self.figure2.add_subplot(111)

        # Retrim
        # cut_time = start + pd.to_timedelta(float_val, unit='m')
        start_time = self.cycle_times_df['Start'][self.current_cycle_index]
        start_cut = start_time + pd.to_timedelta(\
            self.cycle_times_df['Regression Start Time'][n-1],unit='m')
        end_cut = start_time + pd.to_timedelta(\
            self.cycle_times_df['Regression End Time'][n-1],unit='m')
        f_center = f[(f.index > start_cut) & (f.index < end_cut)]
        if 'Accumulated CO2 Absorbed [mol]' in f.columns:
            ax2.plot(f_center['Residence Time [s]'], f_center['ln[CO2]'],\
                      label=f'Cycle #{n}')
            # Plot the fitted line from cycle_times_df
            k = self.cycle_times_df['Rate Constant K (Wet)'][n-1]
            # lnco2_t0 = self.cycle_times_df['lnCO2_t0'][n-1]
            r2 = self.cycle_times_df['Wet Kinetics Regression R2'][n-1]\
                if 'Wet Kinetics Regression R2' in self.cycle_times_df.columns else None
            if isfinite(k): #and isfinite(lnco2_t0):
                x_fit = f_center['Residence Time [s]'].values
                y_fit = (-k * x_fit) +  self.constant_lnco2_0
                #lnco2_t0  # Correct sign for -k
                label = f"Fit: ln[CO2] = -{k:.3f}·t + {self.constant_lnco2_0:.3f}\
                    (R² = {r2:.3f})" if r2 is not None and isfinite(r2)\
                    else "Fit: ln[CO2] = -k·t + ln[CO2]_0"
                ax2.plot(x_fit, y_fit, '--', color='red', label=label)
            ax2.set_xlabel("Residence Time [s]")
            ax2.set_title(f'Cycle #{n} Kinetics Regression')
            ax2.set_ylabel("ln[CO2]")
            ax2.legend()
            ax2.grid(True)
        self.figure2.tight_layout(pad=1)
        self.canvas2.draw()

    def calculate_secondary(self):
        """Calculate variables which only depend on df"""
        print('calculating secondary')

        self.df['TimeDiff'] = self.df.index.diff()
        self.cycle_label.setText(f'{self.cycle_numbers[self.current_cycle_index]}/{max(self.cycle_numbers)}')

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

        correction = float(self.analysis.state_text['Reactor Input Ratio (%)'])\
            /float(self.analysis.state_text['QMS Input Ratio (%)'])  
        self.df['yCO2 [%]'] = self.df[co2_ref_col] * correction * 100
        input_flow_rate_sccm = float(self.analysis.state_text['Input Flow Rate [SCCM]'])
        input_flow_rate_molar = input_flow_rate_sccm * sccm_to_molar
        co2_input_flow_rate_molar = input_flow_rate_molar\
              * float(self.analysis.state_text['Reactor Input Ratio (%)']) / 100
        self.df['[CO2]']=self.df['yCO2 [%]']/100*reactor_pressure\
            /gas_constant_r/reactor_temp_k
        self.df['ln[CO2]'] = log(self.df['[CO2]'])
        self.df['CO2 Partial Flow Rate Out [mol/s]']\
              = self.df['yCO2 [%]']/100* input_flow_rate_molar
        self.df['CO2 Absorbed [mol]']\
              = maximum((co2_input_flow_rate_molar\
                          - self.df['CO2 Partial Flow Rate Out [mol/s]'])\
                              * self.df['TimeDiff'].dt.total_seconds(), 0)
        return

    def calculate_sorption(self):
        """Calculate variables which rely on df and cycle_times_df"""

        #Preliminary calculations
        co2_molar_mass = 44.01
        sorbent_vol = float(self.analysis.state_text['Sorbent Mass [g]'])\
              / float(self.analysis.state_text['Sorbent Bulk Density [g/mL]'])
        sorbent_mass = float(self.analysis.state_text['Sorbent Mass [g]'])
        
        #Instantiate return lists
        min_gammas = []
        total_absorbed = []
        duration_seconds = []

        #Calculate capacity for each cycle in the run
        for n in self.cycle_numbers:
            #Prep data frame
            f = self.df
            #If using baldy3 data, further trim set
            if 'Cycle Identifier' in self.df.columns:
                f = self.df[(self.df['Cycle Identifier'] == 3) & \
                            (self.df['No Completed Cycles'] == n)]
            #Cut the single cycle dataframe based on sorption_start/end_cut
            start_time = self.cycle_times_df['Start'][n-1]
            start_cut = start_time + pd.to_timedelta(\
                self.cycle_times_df['Sorption Start Time'][n-1],unit='m')
            end_cut = start_time + pd.to_timedelta(\
                self.cycle_times_df['Sorption End Time'][n-1],unit='m')
            f = f[(f.index > start_cut) & (f.index < end_cut)]
            f_absorbed = f[(f.index > start_cut) & (f.index < end_cut)]
            total_absorbed.append(sum(f_absorbed['CO2 Absorbed [mol]']))
            min_gammas.append(f['yCO2 [%]'][f['yCO2 [%]'] > 0].min()/100)
            duration_seconds.append((end_cut - start_cut).total_seconds())

        sorption_durations = [
            f"{int(ds // 3600)}:{int((ds % 3600) // 60):02d}:{int(ds % 60):02d}"\
                if pd.notna(ds) else nan
            for ds in duration_seconds
        ]

        #Push return lists to the cycle times dataframe
        self.cycle_times_df['Sorption Duration'] = sorption_durations
        self.cycle_times_df['Highest Sorption Point'] = min_gammas
        self.cycle_times_df['Experimental CO2absorbed [mol]'] = total_absorbed
        self.cycle_times_df['Experimental CO2absorbed [g]']\
              = self.cycle_times_df['Experimental CO2absorbed [mol]'] * co2_molar_mass
        self.cycle_times_df['Sorbent Capacity [gCO2/gSorbent]']\
              = self.cycle_times_df['Experimental CO2absorbed [g]'] / sorbent_mass
        self.cycle_times_df['Sorbent Capacity [gCO2/mLReactor]']\
              = self.cycle_times_df['Experimental CO2absorbed [g]'] / sorbent_vol
        self.cycle_times_df['Capacity % to KPI']\
              = self.cycle_times_df['Sorbent Capacity [gCO2/mLReactor]'] / 0.0283
              # ABOVE CONSTANT PULLED FROM EXCEL, UNSURE OF ORIGIN

    def calculate_kinetics_dry(self):
        """Uses the dry kinetics model to calculate the Rate Constant K"""        
        #Define constants 
        reactor_pressure = 101325 #pa
        reactor_temp_c = 55
        reactor_temp_k = reactor_temp_c + 273
        gas_constant_r = 8.3145
        rh_before_reaction = 100
        h20_molar_mass = 18.02
        inch_to_meter = 0.0254
        sccm_to_molar = reactor_pressure * (1e-6) / (60) / gas_constant_r / 273.15
        
        #Propagate calculations using program inputs
        input_flow_rate_sccm = float(self.analysis.state_text['Input Flow Rate [SCCM]'])
        input_flow_rate_molar = input_flow_rate_sccm * sccm_to_molar
        input_flow_rate_meter = input_flow_rate_molar * 8.3145 * reactor_temp_k\
              / reactor_pressure
        co2_flow_rate_sccm = input_flow_rate_sccm\
              * float(self.analysis.state_text['Reactor Input Ratio (%)']) / 100
        co2_flow_rate_molar = co2_flow_rate_sccm * sccm_to_molar
        reactor_area = pi*((float(self.analysis.state_text['Reactor Diameter [in]'])\
              * inch_to_meter / 2)**2)
        sorbent_vol = float(self.analysis.state_text['Sorbent Mass [g]'])\
              / float(self.analysis.state_text['Sorbent Bulk Density [g/mL]'])
        packing_length_cm = sorbent_vol\
              / (pi * (float(self.analysis.state_text['Reactor Diameter [in]'])\
              * inch_to_meter * 50)**2)
        packing_volume = reactor_area * packing_length_cm / 100
        residence_time = packing_volume / input_flow_rate_meter
        ah_before_reaction_gm3 = 6.112 * (e ** ((17.67*reactor_temp_c)\
              /(reactor_temp_c+243.5))) * rh_before_reaction * h20_molar_mass \
              / reactor_temp_k / 100 / 0.08314
        ah_before_reaction = ah_before_reaction_gm3 / h20_molar_mass
        co2_fraction_before = float(self.analysis.state_text['Reactor Input Ratio (%)'])\
              / 100
        
        #Below will be arrays if there are multiple cycles
        co2_fraction_after = self.cycle_times_df['Highest Sorption Point']
        co2_consumed = co2_flow_rate_molar * (co2_fraction_before - co2_fraction_after)\
            / co2_fraction_before / input_flow_rate_meter
        ah_after_reaction = ah_before_reaction - co2_consumed
        co2_before_reaction = co2_flow_rate_molar / input_flow_rate_meter
        co2_after_reaction = co2_before_reaction - co2_consumed
        rate_constant_k_dry = (log(co2_after_reaction / ah_after_reaction)\
             - log(co2_before_reaction / ah_before_reaction))\
             / (ah_before_reaction - co2_before_reaction) / (-residence_time)
        
        #Push the rate constant to cycle_times_df
        self.cycle_times_df['Rate Constant K (Dry)'] = rate_constant_k_dry

    def calculate_kinetics_wet(self):
        """Uses the wet kinetics odel to calculate the Rate Constant K and related"""
        cycle_times_df = self.cycle_times_df
        df = self.df

        #Setup new columns to be populated
        df['Accumulated CO2 Absorbed [mol]'] = nan
        df['Volume of Active Sorbent [mL]'] = nan
        df['Residence Time [s]'] = nan
        rate_constants = []
        r2s = []

        #Calculate some experimental constants which are not cycle specific
        sorbent_vol = float(self.analysis.state_text['Sorbent Mass [g]'])\
              / float(self.analysis.state_text['Sorbent Bulk Density [g/mL]'])
        co2_molar_mass = 44.01
        self.constant_lnco2_0 = 1.312488772

        #Perform calculations by iterating across each cycle
        for idx, n in enumerate(self.cycle_numbers):
            if 'No Completed Cycles' in df.columns:
                f = df[df['No Completed Cycles'] == n]
            else:
                f = df
            #Masking from beginning of sorption to end of integration
            cycle_start = cycle_times_df['Start'][n-1]
            # cut_time = start + pd.to_timedelta(float_val, unit='m')
            start_time = cycle_start + pd.to_timedelta(\
                cycle_times_df['Sorption Start Time'][n-1],unit='m')
            end_time = cycle_start + pd.to_timedelta(\
                cycle_times_df['Regression End Time'][n-1],unit='m')
            
            mask = (f.index >= start_time) & (f.index <= end_time)
            # Compute cumulative sum for the masked slice
            absorbed_cumsum = f.loc[mask, 'CO2 Absorbed [mol]'].cumsum()
            if len(absorbed_cumsum > 0):
                sorbent_active_volume = sorbent_vol - \
                    (absorbed_cumsum * co2_molar_mass \
                     / (absorbed_cumsum.iloc[-1] * co2_molar_mass/ sorbent_vol))
            else: 
                sorbent_active_volume = sorbent_vol - \
                    (absorbed_cumsum * co2_molar_mass \
                    / cycle_times_df['Sorbent Capacity [gCO2/mLReactor]'][n-1])
            residence_time = sorbent_active_volume\
                  / float(self.analysis.state_text['Input Flow Rate [SCCM]']) * 60
            # Insert the cumulative sum into the main df for the same indices
            df.loc[f.loc[mask].index, 'Accumulated CO2 Absorbed [mol]']\
                  = absorbed_cumsum
            df.loc[f.loc[mask].index, 'Volume of Active Sorbent [mL]']\
                  = sorbent_active_volume
            df.loc[f.loc[mask].index, 'Residence Time [s]'] = residence_time

            # Further trim the area to within the regression region
            # cut_time = start + pd.to_timedelta(float_val, unit='m')
            start_time = cycle_start + pd.to_timedelta(\
                cycle_times_df['Regression Start Time'][n-1],unit='m')
            end_time = cycle_start + pd.to_timedelta(\
                cycle_times_df['Regression End Time'][n-1],unit='m')

            f = f[(f.index > start_time) & (f.index < end_time)]
            # Linear regression: ln[CO2] = -k*t + intercept
            x = residence_time[f.index].values
            y = f['ln[CO2]'].values
            if len(x) > 1:
                # Force fit with constant y-intercept (constant_lnco2_0)
                # y = -k * x + constant_lnco2_0 => y - constant_lnco2_0 = -k * x
                y_adj = y - self.constant_lnco2_0
                # Fit slope only
                try:
                    slope, _, r_value, p_value, std_err = linregress(x, y_adj)
                    rate_constant_k = -slope
                    regression_r2 = r_value ** 2
                except ValueError:
                    rate_constant_k = 0
                    regression_r2 = 0
                # lnCO2_t0 = constant_lnco2_0  # Forced intercept
            else:
                rate_constant_k = nan
                regression_r2 = nan
            # Save to lists for this cycle
            rate_constants.append(rate_constant_k)
            # lnco2_t0s.append(lnCO2_t0)
            r2s.append(regression_r2)
        # Save to cycle_times_df for all cycles
        self.cycle_times_df['Rate Constant K (Wet)'] = rate_constants
        # self.cycle_times_df['lnCO2_t0'] = lnco2_t0s
        self.cycle_times_df['Wet Kinetics Regression R2'] = r2s
        return
    
    #Function to override home button function in matplotlib toolbox
    def on_home_clicked(self):
        self.ax1.autoscale()
        self.canvas1.draw()
        xlims = (tuple(float(x) for x in self.ax1.get_xlim()))
        ylims = (tuple(float(x) for x in self.ax1.get_ylim()))
        self.xlim[self.current_cycle_index] = xlims
        self.ylim[self.current_cycle_index] = ylims
    
    #Button function to view previous cycle
    def select_prev_cycle(self):
        if self.current_cycle_index > 0:
            xlims = (tuple(float(x) for x in self.ax1.get_xlim()))
            ylims = (tuple(float(x) for x in self.ax1.get_ylim()))
            self.xlim[self.current_cycle_index] = xlims
            self.ylim[self.current_cycle_index] = ylims
            self.current_cycle_index -= 1
            self.cycle_label.setText(\
                f'{self.cycle_numbers[self.current_cycle_index]}/{max(self.cycle_numbers)}')
            self.update_plots()

    #Button function to view next cycle
    def select_next_cycle(self):
        if self.current_cycle_index < len(self.cycle_numbers) - 1:
            xlims = (tuple(float(x) for x in self.ax1.get_xlim()))
            ylims = (tuple(float(x) for x in self.ax1.get_ylim()))
            self.xlim[self.current_cycle_index] = xlims
            self.ylim[self.current_cycle_index] = ylims
            self.previous_cycle_index = self.current_cycle_index
            self.current_cycle_index += 1
            self.cycle_label.setText(\
                f'{self.cycle_numbers[self.current_cycle_index]}/{max(self.cycle_numbers)}')
            self.update_plots()
            
    #Calculate scaling factors for selected columns based on sorption range
    def calculate_scaling_factors(self, f, selected_cols, sorption_start, sorption_end):
        # Only describe numeric columns in the sorption range
        describe_df = f.loc[(f.index >= sorption_start) & (f.index <= sorption_end)\
                            , selected_cols].select_dtypes(include=[number]).describe()
        scaling = (describe_df.loc['max']).apply(
            lambda x: 10**(floor(log10(abs(x)))) if x != 0 else 1
        ).fillna(1)
        return scaling.to_dict()

    def get_all_figures_for_pdf(self):
        """Return a list of matplotlib Figure objects for all cycles"""
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
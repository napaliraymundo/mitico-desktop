from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QListWidget, QVBoxLayout,
    QHBoxLayout, QSizePolicy, QApplication, QCheckBox, QPushButton
)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import ast
from numpy import number, floor, log10

class DataViewer(QMainWindow):
    def __init__(self, analysis):
        super().__init__()
        self.analysis = analysis

        self.setWindowTitle("Graph Run")
        screen_geometry = QApplication.desktop().screenGeometry()
        self.setGeometry(300, 0, screen_geometry.width() - 300, screen_geometry.height())
        self.setWindowFlags(self.windowFlags() | Qt.Window)

        # Central layout setup
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # Left panel: Plot + Toolbar
        plot_panel = QVBoxLayout()
        self.figure = Figure(figsize=(8, 6))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.toolbar = NavigationToolbar(self.canvas, self)

        plot_panel.addWidget(self.toolbar)
        plot_panel.addWidget(self.canvas)
        main_layout.addLayout(plot_panel, stretch=4)

        # Right panel: Controls
        control_panel = QVBoxLayout()

        self.compound_list = QListWidget()
        self.compound_list.setSelectionMode(QListWidget.MultiSelection)
       
        # Enable (select) all compounds by default
        self.compound_list.selectAll()
        control_panel.addWidget(QLabel("Compounds"))
        control_panel.addWidget(self.compound_list)

        self.reactor_param_list = QListWidget()
        self.reactor_param_list.setSelectionMode(QListWidget.MultiSelection)
        control_panel.addWidget(QLabel("Reactor Parameters"))
        control_panel.addWidget(self.reactor_param_list)

        self.other_param_list = QListWidget()
        self.other_param_list.setSelectionMode(QListWidget.MultiSelection)
        control_panel.addWidget(QLabel("Other Parameters"))
        control_panel.addWidget(self.other_param_list)

        self.scaling_checkbox = QPushButton("Apply Scaling Factors")
        self.scaling_checkbox.setCheckable(True)
        self.scaling_checkbox.setChecked(True)
        control_panel.addWidget(self.scaling_checkbox)
        self.scaling_checkbox.toggled.connect(self.update_plot)

        control_panel.addStretch()
        main_layout.addLayout(control_panel, stretch=1)

        # Trigger plot updates
        self.compound_list.itemSelectionChanged.connect(self.update_plot)
        self.reactor_param_list.itemSelectionChanged.connect(self.update_plot)
        self.other_param_list.itemSelectionChanged.connect(self.update_plot)

    def calculate_scaling_factors(self):
        # Only describe numeric columns
        describe_df = self.analysis.mdf.select_dtypes(include=[number]).describe()
        describe_df = describe_df.drop(columns=["TimeDiff"], errors="ignore")
        scaling = (describe_df.loc['max']).apply(
            lambda x: 10**(floor(log10(abs(x)))) if x != 0 else 1
        ).fillna(1)
        return scaling.to_dict()

    def get_selected_items(self, widget):
        return [item.text() for item in widget.selectedItems() if item.text() != "None"]
    
    def load_row(self):
        if self.analysis.loaded_row != '':
            # Select and enable only the compounds listed in loaded_row['Selected Compounds']
            selected_compounds = ast.literal_eval(self.analysis.loaded_row.get('Selected Compounds', []))
            for i in range(self.compound_list.count()):
                self.compound_list.item(i).setSelected(self.compound_list.item(i).text() in selected_compounds)
            selected_parameters = ast.literal_eval(self.analysis.loaded_row.get('Selected Parameters', []))
            for i in range(self.reactor_param_list.count()):
                self.reactor_param_list.item(i).setSelected(self.reactor_param_list.item(i).text() in selected_parameters)
            selected_others = ast.literal_eval(self.analysis.loaded_row.get('Selected Others', []))
            for i in range(self.other_param_list.count()):
                self.other_param_list.item(i).setSelected(self.other_param_list.item(i).text() in selected_others)
            scale_run_graph = bool(ast.literal_eval(self.analysis.loaded_row.get('Scale Run Graph', 'False')))
            self.scaling_checkbox.setChecked(scale_run_graph)

    def update_data(self):
        # Block signals to avoid recursion when reloading lists
        self.compound_list.blockSignals(True)
        self.reactor_param_list.blockSignals(True)
        self.other_param_list.blockSignals(True)

         # Only add compounds that are not all NaN
        for item in self.analysis.compound_list:
            if self.analysis.mdf[item].notna().any():
                self.compound_list.addItem(item)
        self.reactor_param_list.addItems(self.analysis.reactor_parameters)
        self.other_param_list.addItems(self.analysis.other_parameters)

        # Reload compound list
        self.compound_list.clear()
        for item in self.analysis.compound_list:
            if self.analysis.mdf[item].notna().any():
                self.compound_list.addItem(item)

        # Reload reactor param list
        self.reactor_param_list.clear()
        self.reactor_param_list.addItems(self.analysis.reactor_parameters)

        # Reload other param list
        self.other_param_list.clear()
        self.other_param_list.addItems(self.analysis.other_parameters)

        # Rebuild scaling factors
        self.scaling_factors = self.calculate_scaling_factors()

        # Re-enable signals
        self.compound_list.blockSignals(False)
        self.reactor_param_list.blockSignals(False)
        self.other_param_list.blockSignals(False)


    def update_plot(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        use_scaling = self.scaling_checkbox.isChecked()

        selected_compounds = self.get_selected_items(self.compound_list)
        selected_reactor = self.get_selected_items(self.reactor_param_list)
        selected_other = self.get_selected_items(self.other_param_list)
        all_selected = selected_compounds + selected_reactor + selected_other

        for entry in all_selected:
            if entry in self.analysis.mdf.columns:
                if use_scaling and entry in self.scaling_factors:
                    scaled_data = self.analysis.mdf[entry] / self.scaling_factors[entry]
                    label = f"{entry} / {self.scaling_factors[entry]:.1e}"
                    index = self.analysis.mdf.index
                    ax.plot((index - index[0]).total_seconds()/60, scaled_data, label=label)
                else:
                    index = self.analysis.mdf.index
                    ax.plot((index - index[0]).total_seconds()/60, self.analysis.mdf[entry], label=entry)

        # Set white background for axes and figure
        ax.set_facecolor("white")
        self.figure.set_facecolor("white")

        # Add axis labels and title
        ax.set_xlabel("Elapsed Time (min)")
        ax.set_ylabel("Concentration")

        # Embedded title and label
        ax.legend()
        ax.grid(True, color="gray", linestyle="--")

        self.figure.tight_layout(pad=1)
        self.canvas.draw()
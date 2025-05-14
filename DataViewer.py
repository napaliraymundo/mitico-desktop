from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QLabel, QListWidget, QVBoxLayout,
    QHBoxLayout, QSizePolicy, QApplication, QCheckBox
)
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import numpy as np
import pandas as pd

class DataViewer(QMainWindow):
    def __init__(self, df, parameters, compounds, other):
        super().__init__()
        self.df = df
        self.parameters = parameters
        self.compounds = compounds
        self.other = other

        self.setWindowTitle("Data Viewer")
        screen_geometry = QApplication.desktop().screenGeometry()
        self.setGeometry(300, 0, screen_geometry.width() - 300, screen_geometry.height())
        self.setWindowFlags(self.windowFlags() | Qt.Window)

        # === Compute scaling factors for all numeric columns ===
        self.scaling_factors = self._calculate_scaling_factors()

        # Central layout setup
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)

        # Left panel: Plot + Toolbar
        plot_panel = QVBoxLayout()
        self.figure = Figure(figsize=(8, 6), facecolor="#121212")
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
        self.compound_list.addItems(self.compounds)
        control_panel.addWidget(QLabel("Compounds"))
        control_panel.addWidget(self.compound_list)

        self.reactor_param_list = QListWidget()
        self.reactor_param_list.setSelectionMode(QListWidget.MultiSelection)
        self.reactor_param_list.addItems(self.parameters)
        control_panel.addWidget(QLabel("Reactor Parameters"))
        control_panel.addWidget(self.reactor_param_list)

        self.other_param_list = QListWidget()
        self.other_param_list.setSelectionMode(QListWidget.MultiSelection)
        self.other_param_list.addItems(self.other)
        control_panel.addWidget(QLabel("Other Parameters"))
        control_panel.addWidget(self.other_param_list)

        # === Add Use Scaling Checkbox ===
        self.scaling_checkbox = QCheckBox("Use Scaling Factors")
        control_panel.addWidget(self.scaling_checkbox)

        control_panel.addStretch()
        main_layout.addLayout(control_panel, stretch=1)

        # Trigger plot updates
        self.compound_list.itemSelectionChanged.connect(self.update_plot)
        self.reactor_param_list.itemSelectionChanged.connect(self.update_plot)
        self.other_param_list.itemSelectionChanged.connect(self.update_plot)
        self.scaling_checkbox.stateChanged.connect(self.update_plot)

        self.update_plot()

    def _calculate_scaling_factors(self):
        # Only describe numeric columns
        describe_df = self.df.select_dtypes(include=[np.number]).describe()
        describe_df = describe_df.drop(columns=["TimeDiff"], errors="ignore")
        scaling = (describe_df.loc['max']).apply(
            lambda x: 10**(np.floor(np.log10(abs(x)))) if x != 0 else 1
        ).fillna(1)
        return scaling.to_dict()

    def get_selected_items(self, widget):
        return [item.text() for item in widget.selectedItems() if item.text() != "None"]

    def update_plot(self):
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        use_scaling = self.scaling_checkbox.isChecked()

        selected_compounds = self.get_selected_items(self.compound_list)
        selected_reactor = self.get_selected_items(self.reactor_param_list)
        selected_other = self.get_selected_items(self.other_param_list)
        all_selected = selected_compounds + selected_reactor + selected_other

        for entry in all_selected:
            if entry in self.df.columns:
                if use_scaling and entry in self.scaling_factors:
                    scaled_data = self.df[entry] / self.scaling_factors[entry]
                    label = f"{entry} / {self.scaling_factors[entry]:.1e}"
                    ax.plot(self.df.index, scaled_data, label=label)
                else:
                    ax.plot(self.df.index, self.df[entry], label=entry)

        # Embedded title and label
        ax.legend()
        ax.grid(True, color="gray", linestyle="--")

        self.figure.tight_layout(pad=1)
        self.canvas.draw()
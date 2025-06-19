from PyQt5.QtWidgets import QWidget, QListWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem
from PyQt5.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import pandas as pd

class TableViewer(QWidget):
    def __init__(self, analysis):
        super().__init__()
        self.analysis = analysis
        if 'No Completed Cycles' in self.analysis.mdf.columns:
            self.cycle_numbers = self.analysis.mdf['No Completed Cycles'].dropna().unique()
            multi_cycle = True
        else: 
            multi_cycle = False

        main_layout = QHBoxLayout(self)

        # Add table displaying cycle_times_df
        self.table = QTableWidget()

        # Add bottom plot (Sorption Metrics)
        plot_panel = QVBoxLayout()
        self.figure2 = Figure(figsize=(12, 4))
        self.canvas2 = FigureCanvas(self.figure2)
        self.toolbar2 = NavigationToolbar(self.canvas2, self)
        plot_panel.addWidget(self.toolbar2)
        plot_panel.addWidget(self.canvas2)

        # Add selectable columns list
        self.param_list = QListWidget()
        self.param_list.setSelectionMode(QListWidget.MultiSelection)
        # Use all columns except 'Cycle' as selectable metrics
        selectable_cols = [col for col in self.analysis.cycle_times_df.columns if col != 'Cycle']
        self.param_list.addItems(selectable_cols)
        for i in range(self.param_list.count()):
            self.param_list.item(i).setSelected(True)
        param_panel = QVBoxLayout()
        param_panel.addWidget(QLabel("Sorption/Desorption Metrics"))
        param_panel.addWidget(self.param_list)

        # Split window: table on top, plot and param list below
        split_layout = QVBoxLayout()
        split_layout.addWidget(self.table, stretch=1)
        bottom_panel = QHBoxLayout()
        bottom_panel.addLayout(plot_panel, stretch=4)
        bottom_panel.addLayout(param_panel, stretch=1)
        split_layout.addLayout(bottom_panel, stretch=1)
        main_layout.addLayout(split_layout)

        # Only connect param_list selection to plot update
        self.param_list.itemSelectionChanged.connect(self.update_plot)
        self.update_table()
        self.update_plot()

    def update_table(self):
        df = self.analysis.cycle_times_df
        self.table.clear()
        self.table.setRowCount(df.shape[1])
        self.table.setColumnCount(df.shape[0])
        self.table.setVerticalHeaderLabels([str(col) for col in df.columns])
        for i in range(df.shape[0]):
            for j, col in enumerate(df.columns):
                value = df.iloc[i][col]
                # Format float to 4 decimals, datetime to short string, else str
                if isinstance(value, float):
                    value_str = f"{value:.4e}"
                elif pd.api.types.is_datetime64_any_dtype(type(value)) or isinstance(value, pd.Timestamp):
                    value_str = pd.to_datetime(value).strftime('%m-%d %H:%M')
                else:
                    value_str = str(value)
                self.table.setItem(j, i, QTableWidgetItem(value_str))
        self.table.resizeColumnsToContents()
        self.table.removeRow(0)

    def reload_dropdown(self):
        self.param_list.clear()
        df = self.analysis.cycle_times_df
        # Only add columns that are numeric or timedelta (for plotting)
        selectable_cols = []
        for col in df.columns:
            if col == 'Cycle':
                continue
            if pd.api.types.is_numeric_dtype(df[col]) or pd.api.types.is_timedelta64_dtype(df[col]):
                selectable_cols.append(col)
        self.param_list.addItems(selectable_cols)
        # Optionally select all by default
        for i in range(self.param_list.count()):
            self.param_list.item(i).setSelected(True)

    def update_plot(self):
        df = self.analysis.cycle_times_df
        self.figure2.clear()
        ax2 = self.figure2.add_subplot(111)
        selected_metrics = [i.text() for i in self.param_list.selectedItems()]
        for metric in selected_metrics:
            if metric in df:
                # Only plot if the column is numeric
                if pd.api.types.is_numeric_dtype(df[metric]):
                    ax2.scatter(df['Cycle'], df[metric], label=metric)
                # Optionally, handle timedelta columns (plot in minutes)
                elif pd.api.types.is_timedelta64_dtype(df[metric]):
                    ax2.scatter(df['Cycle'], df[metric].dt.total_seconds() / 60, label=f"{metric} (min)")
        ax2.set_title("Sorption & Desorption Metrics")
        ax2.set_xlabel("Cycle")
        ax2.legend()
        ax2.grid(True)
        self.figure2.tight_layout()
        self.canvas2.draw()
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem, QApplication, QLabel
from PyQt5.QtCore import Qt
import pandas as pd

class RawDataViewer(QMainWindow):
    def __init__(self, mdf):
        super().__init__()
        self.setWindowTitle("Raw Data Table")
        screen_geometry = QApplication.desktop().screenGeometry()
        self.setGeometry(300, 0, screen_geometry.width() - 300, screen_geometry.height())
        self.setWindowFlags(self.windowFlags() | Qt.Window)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        table = QTableWidget()
        # Only show the first 1000 rows to prevent UI issues with large files
        df = mdf.reset_index().iloc[:1000]
        table.setRowCount(df.shape[0])
        table.setColumnCount(df.shape[1])
        table.setHorizontalHeaderLabels([str(col) for col in df.columns])
        for i in range(df.shape[0]):
            for j, col in enumerate(df.columns):
                value = df.iloc[i][col]
                if isinstance(value, float):
                    value_str = f"{value:.4f}"
                elif pd.api.types.is_datetime64_any_dtype(type(value)) or isinstance(value, pd.Timestamp):
                    value_str = pd.to_datetime(value).strftime('%m-%d %H:%M:%S')
                else:
                    value_str = str(value)
                table.setItem(i, j, QTableWidgetItem(value_str))
        # table.resizeColumnsToContents()
        layout.addWidget(table)
        # Optionally, add a note if not all rows are shown
        if mdf.shape[0] > 1000:
            note = QLabel(f"Showing first 1000 of {mdf.shape[0]} rows.")
            layout.addWidget(note)

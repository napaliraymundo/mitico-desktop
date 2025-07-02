import os
import pandas as pd
from numpy import nan, unique, insert

class MassSpecParser:
    def __init__(self, analysis):
        self.filepath = analysis.filepath
        self.filename = analysis.filename
        self.header_row_number = None
        self.start_datetime = None

    def parse(self):
        with open(self.filepath, 'r') as f:
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
            self.filepath, header=self.header_row_number, encoding='unicode_escape')

        # Use ms column to calculate datetime. Set as dataframe index
        mdf['Datetime'] = self.start_datetime + \
            pd.to_timedelta(mdf['ms'], unit='ms')
        mdf = mdf.set_index('Datetime')

        # Tweak columns and generate a list of compounds
        mdf = mdf.drop(['Time', 'ms'], axis=1)
        compound_list = list(mdf.columns)

        start_time = mdf.index[0]
        end_time = mdf.index[-1]
        cycle_times = []
        cycle_times.append({'Cycle': 1,
                                'Start': start_time, 'End': end_time})
        cycle_times_df = pd.DataFrame(cycle_times)

        return mdf, compound_list, cycle_times_df


class Baldy2Parser:
    def __init__(self, mdf, file_path):
        self.mdf = mdf
        self.file_path = file_path

    def parse(self):
        # Read the temp CSV (no header)
        temp_df = pd.read_csv(self.file_path, header=None)
        # Assume columns: Date, Time, T1, T2, T3, T4, T5
        temp_df.columns = ['Date', 'Time', 'T1', 'T2', 'T3', 'T4']

        # Replace "OL" with nan in all temperature columns, make float
        temp_columns = ['T1', 'T2', 'T3', 'T4']
        temp_df[temp_columns] = temp_df[temp_columns].replace("OL", nan)
        temp_df[temp_columns] = temp_df[temp_columns].astype(float)

        # Combine date and time, parse to datetime
        temp_df['Datetime'] = pd.to_datetime(temp_df['Date'] + ' ' + temp_df['Time'])
        temp_df = temp_df.set_index('Datetime')

        # Drop original date/time columns
        temp_df = temp_df.drop(['Date', 'Time'], axis=1)
        # Drop temperature columns that are all NaN
        temp_df = temp_df.dropna(axis=1, how='all')
        # Update temp_columns to reflect dropped columns
        temp_columns = [col for col in temp_columns if col in temp_df.columns]

        # Merge with mdf on nearest timestamp (tolerance 10s)
        df = pd.merge_asof(
            self.mdf.sort_index(), 
            temp_df.sort_index(), 
            left_index=True, 
            right_index=True, 
            direction='nearest', 
            tolerance=pd.Timedelta(seconds=10)
        )

        return df, temp_columns

class BackendParser:
    def __init__(self, mdf, start_datetime, duration, filename, folder_path):
        self.folder_path = folder_path
        self.filename = filename
        self.mdf = mdf
        self.start_datetime = start_datetime
        self.duration = duration

    def parse(self):
        # Select backend files corresponding to the dates in the selected mass spec file
        dates_to_pull = unique(self.mdf.index.date)
        dates_to_pull = insert(dates_to_pull,0,
                                    dates_to_pull.min() - pd.Timedelta(days=1))
        backend_filenames = \
        [f"data_{date.strftime('%Y-%m-%d')}.csv" for date in dates_to_pull]

        # Concatenate all requisite files and clean columns
        try:
            backend_dataframes = \
                [pd.read_csv(os.path.join(self.folder_path,f)) for f in backend_filenames]
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
        return df, reactor_parameters, cycle_times_df
    
def save_pdf_report(analysis):
    """Export a PDF report with run parameters, cycle_times_df, and all current plot images."""
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak, KeepTogether
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    import io

    # Prompt user for save location
    from PyQt5.QtWidgets import QFileDialog, QMessageBox
    file_path, _ = QFileDialog.getSaveFileName(analysis, "Save PDF Report", f"{analysis.filename} Exp Report.pdf", "PDF Files (*.pdf)")
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
        ("Sorbent Mass [g]", analysis.sorbent_mass_input.text()),
        ("Reactor Diameter [in]", analysis.reactor_diameter_input.text()),
        ("Sorbent Bulk Density [g/mL]", analysis.bulk_density_input.text()),
        ("Packing Factor", analysis.packing_factor_input.text()),
        ("Input Flow Rate [SCCM]", analysis.input_flow_rate_input.text()),
        ("Reference Gas", analysis.reference_gas_dropdown.currentText()),
        ("Reactor Input Ratio (%)", analysis.reactor_input_ratio_input.text()),
        ("QMS Input Ratio (%)", analysis.qms_input_ratio_input.text()),
        ("Sorption Start (%)", analysis.sorption_start_input.text()),
        ("Sorption End (%)", analysis.sorption_end_input.text()),
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
    if analysis.cycle_times_df is not None and not analysis.cycle_times_df.empty:
        elements.append(Paragraph("Cycle Times Table", styleH))
        df = analysis.cycle_times_df.reset_index(drop=True)
        import pandas as pd
        def fmt(x, col=None):
            if isinstance(x, float):
                return f"{x:.2e}" if x != 0 else "0"
            if col == 'Sorption Duration':
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
    if hasattr(analysis, 'cycle_instance') and analysis.cycle_instance is not None:
        try:
            figures = analysis.cycle_instance.get_all_figures_for_pdf()
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
                    fig.savefig(buf, format='png', bbox_inches='tight', dpi=500)
                    buf.seek(0)
                    img = Image(buf, width=full_plot_width, height=full_plot_height)
                    imgs.append(img)
                    buffers.append(buf)
                elements.append(KeepTogether(imgs))
                elements.append(Spacer(1, 12))
                elements.append(PageBreak())

    # Add DataViewer plot if available (make it full page)
    if hasattr(analysis, 'viewer_instance') and analysis.viewer_instance is not None:
        try:
            fig = analysis.viewer_instance.figure
            for ax in fig.get_axes():
                for item in ([ax.title, ax.xaxis.label, ax.yaxis.label] + ax.get_xticklabels() + ax.get_yticklabels() + ax.get_legend().get_texts() if ax.get_legend() else []):
                    item.set_fontsize(8)
            buf = io.BytesIO()
            fig.set_size_inches(full_plot_width / 96, (full_plot_width * 0.6) / 96)
            fig.savefig(buf, format='png', bbox_inches='tight', dpi=500)
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
    if hasattr(analysis, 'metrics_instance') and analysis.metrics_instance is not None:
        try:
            fig = analysis.metrics_instance.figure
            for ax in fig.get_axes():
                for item in ([ax.title, ax.xaxis.label, ax.yaxis.label] + ax.get_xticklabels() + ax.get_yticklabels() + ax.get_legend().get_texts() if ax.get_legend() else []):
                    item.set_fontsize(8)
            buf = io.BytesIO()
            fig.set_size_inches(full_plot_width / 96, (full_plot_width * 0.6) / 96)
            fig.savefig(buf, format='png', bbox_inches='tight', dpi=500)
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
        QMessageBox.critical(analysis, "PDF Export Error", f"Failed to save PDF: {e}")
        return
    finally:
        for buf in buffers:
            buf.close()

    # Success message
    QMessageBox.information(analysis, "PDF Exported", f"PDF report saved to:\n{file_path}")
import os
import pandas as pd
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


# class Baldy2Parser:
#     def __init__(self, mdf, file_path):
#         self.__init__
    
#     def parse()

class BackendParser:
    def __init__(self, mdf, start_datetime, duration, filename, folder_path):
        self.folder_path = folder_path
        self.filename = filename
        self.mdf = mdf
        self.start_datetime = start_datetime
        self.duration = duration

    def parse(self):
        if self.start_datetime == 'Start Date: ':
            raise ValueError('Please select valid QMS file first')
        else:
            # Select backend files corresponding to the dates in the selected mass spec file
            dates_to_pull = np.unique(self.mdf.index.date)
            dates_to_pull = np.insert(dates_to_pull,0,
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

            load_run_parameters(self, self.filename)

            sccm_to_molar = (1/60) * (1/22414)
            df['TimeDiff'] = df.index.diff()
            df['flue_flow_in[sccm/s]'] = df['MFC1.Massflow'] + df['MFC2.Massflow'] + df['MFC3.Massflow'] + df['MFC4.Massflow']
            df['flue_flow_in[mol/s]'] = df['flue_flow_in[sccm/s]'] * sccm_to_molar
            df['CO2_flow_in[mol/s]'] = df['MFC4.Massflow'] * sccm_to_molar
            df['CO2 / N2'] = df['Carbon dioxide'] / df['Nitrogen']
            correction = self.co2_ratio_input / self.mass_spec_co2_ratio
            df['yCO2'] = df['CO2 / N2'] * correction
            df['CO2_flow_out[mol/s]'] = df['yCO2'] * df['flue_flow_in[mol/s]']
            df['CO2absorbed[mol]'] = (df['CO2_flow_in[mol/s]'] - df['CO2_flow_out[mol/s]']) * df['TimeDiff'].dt.total_seconds()
            
            other_parameters = ['flue_flow_in[sccm/s]','flue_flow_in[mol/s]','CO2_flow_in[mol/s]','CO2 / N2','yCO2',
                                'CO2_flow_out[mol/s]','co2absorbed[mol]']

            return df, reactor_parameters, other_parameters, cycle_times_df
        
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
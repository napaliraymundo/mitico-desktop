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
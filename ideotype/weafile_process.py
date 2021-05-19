"""Read in hourly weather file."""

import os
import glob
import yaml
from datetime import datetime

import numpy as np
import pandas as pd

from ideotype import DATA_PATH
from ideotype.utils import CC_RH


def read_wea(year_start, year_end):
    """
    Read in raw hourly weather data.

    - Data source: NOAA Integrated Surface Hourly Database
    - Link: https://www.ncdc.noaa.gov/isd
    - Weather data: temperature, RH, precipitation

    Parameters
    ----------
    year_start : int
    year_end : int

    """
    # setting up np.read_fwf arguments
    colnames = ['time',
                'temp', 'temp_quality',
                'dew_temp', 'dtemp_quality',
                'precip', 'precip_time',
                'precip_depth', 'precip_quality',
                'precip_perhr', 'rh']
    colspecs = [(15, 25),  # time
                (87, 92),  # temp
                (92, 93),  # temp_quality
                (93, 98),  # dew_temp
                (98, 99),  # dtemp_quality
                (105, 8193)]  # precip string

    # Read in relevant file paths
    fpaths_wea = os.path.join(DATA_PATH, 'files', 'filepaths_wea.yml')
    with open(fpaths_wea) as pfile:
        dict_fpaths = yaml.safe_load(pfile)

    # Read in info on conversion between WBAN & USAF id numbering system
    fpath_id_conversion = os.path.join(DATA_PATH,
                                       *dict_fpaths['id_conversion'])
    df_stations = pd.read_csv(fpath_id_conversion, header=None, dtype=str)
    df_stations.columns = ['WBAN', 'USAF']

    # Set up basepath
    basepath = dict_fpaths['basepath']

    # Set up years
    if year_start == year_end:
        years = [year_start]
    else:
        years = np.arange(year_start, year_end+1)

    # Set up date parser for pandas
    dateparser = lambda dates: [datetime.strptime(d, '%Y%m%d%H') for d in dates]  # noqa

    # Loop through years to read in data
    for year in years:
        print(year)  # track progress

        # Check first if file exists already
        if os.path.isfile(os.path.join(basepath, f'temp_{year}.csv')):
            raise ValueError(f'temp_{year}.csv exists!')

        # Set up default timeline
        season_start = '02-01-'
        season_end = '11-30-'
        times = pd.date_range(f'{season_start + str(year)}',
                              f'{season_end + str(year)} 23:00:00',
                              freq='1H')

        arr_temp_sites = np.zeros(shape=(len(times),))
        arr_rh_sites = np.zeros(shape=(len(times),))
        arr_precip_sites = np.zeros(shape=(len(times),))

        # initiate empty list to store all site ids (USAF)
        siteid_all = []

        # For years 1961-1990
        if year < 1991:
            fnames = glob.glob(
                os.path.join(os.path.expanduser('~'),
                             'data', 'ISH', str(year), '*'))

        # For years 1991-2010
        else:
            # Select class1 weather station sites
            fpath_stations_info = os.path.join(DATA_PATH,
                                               *dict_fpaths['stations_info'])
            df_sites = pd.read_csv(fpath_stations_info)
            sites = df_sites.query(
                'CLASS == 1').reset_index().USAF.astype('str')

            # Select sites within specified year that are class1
            sites_year = glob.glob(
                os.path.join(os.path.expanduser('~'),
                             'data', 'ISH', str(year), '*'))
            sites_year = pd.Series([
                site.split('/')[-1].split('-')[0] for site in sites_year])
            sites_year = sites_year[
                sites_year.isin(sites)].reset_index(drop=True)

            # Drop duplicates in sites_year
            sites_year.drop_duplicates(keep='first', inplace=True)

            fnames = []
            for site in sites_year:
                fname = glob.glob(os.path.join(os.path.expanduser('~'),
                                               'data', 'ISH',
                                               str(year),
                                               f'{site}-*'))
                if len(fname) == 1:
                    fnames.append(fname[0])
                else:
                    print(f'choose from files: {fname}')
                    fname = glob.glob(os.path.join(os.path.expanduser('~'),
                                                   'data', 'ISH',
                                                   str(year),
                                                   f'{site}-99999-*'))
                    fnames.append(fname[0])

        for name in fnames:
            # site_id
            siteid_usaf = name.split('/')[-1].split('-')[0]
            siteid_wban = name.split('/')[-1].split('-')[1]

            if siteid_usaf == '999999':
                siteid_usaf = df_stations.query(
                    f'WBAN == "{siteid_wban}"').USAF.item()

            siteid_all.append(siteid_usaf)

            # Read in fixed width weather data
            df = pd.read_fwf(name,
                             names=colnames,
                             colspecs=colspecs,
                             header=None,
                             index_col='time',
                             encoding='latin_1',
                             dtype={'temp': int, 'precip': str},
                             parse_dates=['time'],
                             date_parser=dateparser)

            # Remove duplicated hours, keeping only first occurrence
            # keep = 'first': marks duplicate as True
            # except for first occurrence
            # ~: not selecting for True ends up selecting
            # for the non-duplicated indexes
            # *** note: can't just use df.index.drop_duplicates() since
            # * that only returns a list of the non-duplicated index
            # * but you can't just use that to select non-duplicated rows
            # * since it will also pick up the duplicated rows
            df = df[~df.index.duplicated(keep='first')]

            # Add in missing time values
            # Correct for leap years
            # Filter only for growing season
            df = df.reindex(times, fill_value=np.nan)

            # Find precip data
            df.precip_time = df[
                df['precip'].str.find('ADDAA1') != -1]['precip'].str.split(
                    'ADDAA1').str.get(1).str.slice(0, 2).astype(float)
            df.precip_depth = df[
                df['precip'].str.find('ADDAA1') != -1]['precip'].str.split(
                    'ADDAA1').str.get(1).str.slice(2, 6).astype(float)
            df.precip_quality = df[
                df['precip'].str.find('ADDAA1') != -1]['precip'].str.split(
                    'ADDAA1').str.get(1).str.slice(7, 8)

            # Filter out weather data based on quality code (data manual p.26)
            # Masking unqualified data with NANs:
            # code 3 (Erroneous) &
            # code 7 (Erroneous, data originated from an NCEI data source)
            # *** temp
            quality_temp = (
                df.temp_quality == '3') | (df.temp_quality == '7')
            rows_temp = df[quality_temp].index
            df.loc[rows_temp, 'temp'] = np.nan
            # *** dew temp
            quality_dtemp = (
                df.dtemp_quality == '3') | (df.dtemp_quality == '7')
            rows_dtemp = df[quality_dtemp].index
            df.loc[rows_dtemp, 'dew_temp'] = np.nan
            # *** precip
            quality_precip = (
                df.precip_quality == '3') | (df.precip_quality == '7')
            rows_precip = df[quality_precip].index
            df.loc[rows_precip, 'precip'] = np.nan

            # Replace missing data with NaN
            df.temp = df.temp.replace({9999: np.nan})
            df.dew_temp = df.dew_temp.replace({9999: np.nan})
            df.precip_time = df.precip_time.replace({99: np.nan})
            df.precip_depth = df.precip_depth.replace({9999: np.nan})

            # Calculate hourly precip depth
            df.precip_perhr = df.precip_depth/df.precip_time

            # Account for cases where precip_hr = 0
            # which produces infinite precip_perhr
            df.precip_perhr = df.precip_perhr.replace({np.inf: np.nan})

            # Unit conversion
            df.temp = np.round(df.temp/10, 2)
            df.dew_temp = np.round(df.dew_temp/10, 2)
            df.precip_perhr = np.round(df.precip_perhr/10, 1)

            # calculating RH through Clausius Clapeyron
            df.rh = CC_RH(df.temp, df.dew_temp)*100
            if df[df.rh > 100].rh.sum() > 100:
                print('rh > 100: ', year, name)

            arr_temp_sites = np.vstack([arr_temp_sites, df.temp])
            arr_rh_sites = np.vstack([arr_rh_sites, df.rh])
            arr_precip_sites = np.vstack([arr_precip_sites, df.precip_perhr])

        # Convert all data for single year into pd.DataFrame
        df_temp_sites = pd.DataFrame(arr_temp_sites.transpose(), index=times)
        df_temp_sites.drop(df_temp_sites.columns[0], axis=1, inplace=True)
        df_temp_sites.columns = siteid_all
        df_temp_sites.sort_index(axis=1, inplace=True)

        df_rh_sites = pd.DataFrame(arr_rh_sites.transpose(), index=times)
        df_rh_sites.drop(df_rh_sites.columns[0], axis=1, inplace=True)
        df_rh_sites.columns = siteid_all
        df_rh_sites.sort_index(axis=1, inplace=True)

        df_precip_sites = pd.DataFrame(
            arr_precip_sites.transpose(), index=times)
        df_precip_sites.drop(df_precip_sites.columns[0], axis=1, inplace=True)
        df_precip_sites.columns = siteid_all
        df_precip_sites.sort_index(axis=1, inplace=True)

        # Output data for each year
        df_temp_sites.to_csv(os.path.join(basepath, f'temp_{year}.csv'))
        df_rh_sites.to_csv(os.path.join(basepath, f'rh_{year}.csv'))
        df_precip_sites.to_csv(os.path.join(basepath, f'precip_{year}.csv'))


def read_solrad(year_start, year_end):
    """
    Read in raw hourly solar radiation data.

    - Data source: NSRDB
    - Source: https://nsrdb.nrel.gov/about/u-s-data.html

    Parameters
    ----------
    year_start : int
    year_end : int

    Returns
    -------
    df_solrad

    """
    # Read in relevant file paths
    fpaths_wea = os.path.join(DATA_PATH, 'files', 'filepaths_wea.yml')
    with open(fpaths_wea) as pfile:
        dict_fpaths = yaml.safe_load(pfile)

    # Set up basepath
    basepath = dict_fpaths['basepath']

    # Read in info on conversion between WBAN & USAF id numbering system
    fpath_id_conversion = os.path.join(DATA_PATH,
                                       *dict_fpaths['id_conversion'])
    df_stations = pd.read_csv(fpath_id_conversion, header=None, dtype=str)
    df_stations.columns = ['WBAN', 'USAF']
    stations_usaf = df_stations.USAF

    # Set up years
    if year_start == year_end:
        years = [year_start]
    else:
        years = np.arange(year_start, year_end+1)

    # Dataframe setup for years 1961-1990
    colnames = ['year', 'month', 'day', 'hour', 'solrad']
    colspecs = [(1, 3), (4, 6), (7, 9), (10, 12), (23, 27)]

    # Loop through years to read in data
    for year in years:
        print(year)  # track progress

        # Check first if file exists already
        if os.path.isfile(os.path.join(basepath, f'solrad_{year}.csv')):
            raise ValueError(f'solrad_{year}.csv exists!')

        # Set up default timeline
        season_start = '02-01-'
        season_end = '11-30-'
        datetimes_season = pd.date_range(
            f'{season_start + str(year)}',
            f'{season_end + str(year)} 23:00:00', freq='1H')

        # Initiate empty array to store data
        arr_solrad_sites = np.zeros(shape=len(datetimes_season),)

        # initiate empty list to store all site ids (USAF)
        siteid_all = []

        # For years 1961-1990
        if year < 1991:
            # Fetch all file names within year
            fnames = glob.glob(
                os.path.join(os.path.expanduser('~'),
                             'data', 'ISH_NSRD', str(year), '*'))

            for name in fnames:
                siteid_wban = name.split('/')[-1].split('_')[0]
                siteid_usaf = df_stations.query(
                    f'WBAN == "{siteid_wban}"').USAF.item()

                siteid_all.append(siteid_usaf)

                # Read in fixed-width data
                df = pd.read_fwf(name,
                                 skiprows=[0],
                                 header=None,
                                 names=colnames,
                                 colspecs=colspecs)

                # Structure date-time info
                datetimes = df.apply(lambda row: datetime(
                    year, row['month'], row['day'], row['hour']-1), axis=1)

                # Fetch solrad - Global Horizontal Radiation (Wh/m2)
                df_solrad = pd.DataFrame(df.solrad)
                df_solrad.index = datetimes

                # Remove duplicated hours, keeping only first occurrence
                # keep = 'first': marks duplicate as True
                # except for first occurrence
                # ~: not selecting for True ends up selecting
                # for the non-duplicated indexes
                df_solrad = df_solrad[
                    ~df_solrad.index.duplicated(keep='first')]

                # Add in missing time values
                # Correct for leap years
                # Filter only for growing season
                df_solrad = df_solrad.reindex(datetimes_season,
                                              fill_value=np.nan)

                # Replace missing data with NaN
                df_solrad.replace({9999: np.nan}, inplace=True)

                arr_solrad_sites = np.vstack(
                    [arr_solrad_sites, df_solrad.solrad])

            # Convert all data for single year into pd.DataFrame
            df_solrad_sites = pd.DataFrame(
                arr_solrad_sites.transpose(), index=datetimes_season)
            df_solrad_sites.drop(
                df_solrad_sites.columns[0], axis=1, inplace=True)
            df_solrad_sites.columns = siteid_all
            df_solrad_sites.sort_index(axis=1, inplace=True)

            # Output data for each year
            df_solrad_sites.to_csv(
                os.path.join(basepath, f'solrad_{year}.csv'))

        # For years 1991-2010:
        else:
            for station in stations_usaf:
                # Search for specified year-site data
                fname = glob.glob(os.path.join(
                    os.path.expanduser('~'),
                    'data', 'ISH_NSRD', str(year), f'{station}_*.csv'))

                if len(fname) == 1:
                    # Read in file
                    df = pd.read_csv(fname[0])
                    siteid_all.append(station)

                else:
                    print('multiple files!', fname)

                # Format date-time info
                dates = df['YYYY-MM-DD']
                hours = df['HH:MM (LST)']
                hours = [int(hour.split(':')[0])-1 for hour in hours]
                datetimes = [datetime.strptime(
                    dates[item] + '-' + str(hours[item]),
                    '%Y-%m-%d-%H') for item in np.arange(df.shape[0])]

                # Fetch solrad - Global Horizontal Radiation (Wh/m2)
                df_solrad = pd.DataFrame(df['METSTAT Glo (Wh/m^2)'])
                df_solrad.columns = ['solrad']
                df_solrad.index = datetimes

                # Remove duplicated hours, keeping only first occurrence
                # keep = 'first': marks duplicate as True
                # except for first occurrence
                # ~: not selecting for True ends up selecting
                # for the non-duplicated indexes
                df_solrad = df_solrad[
                    ~df_solrad.index.duplicated(keep='first')]

                # Add in missing time values
                # Correct for leap years
                # Filter only for growing season
                df_solrad = df_solrad.reindex(datetimes_season,
                                              fill_value=np.nan)

                # Replace missing data with NaN
                df_solrad.replace({9999: np.nan}, inplace=True)

                # Stacking all data as arrays to make sure
                # all dimensions are correct
                arr_solrad_sites = np.vstack(
                    [arr_solrad_sites, df_solrad.solrad])

            # Convert all data for single year into pd.DataFrame
            df_solrad_sites = pd.DataFrame(
                arr_solrad_sites.transpose(), index=datetimes_season)
            df_solrad_sites.drop(
                df_solrad_sites.columns[0], axis=1, inplace=True)
            df_solrad_sites.columns = siteid_all
            df_solrad_sites.sort_index(axis=1, inplace=True)

            # Output data for each year
            df_solrad_sites.to_csv(
                os.path.join(basepath, f'solrad_{year}.csv'))


def combine_wea(basepath):
    """
    Combine weather data for all years.

    Parameters
    ----------
    basepath : str
        path where all weather data csv files are stored.

    """
    csv_files = ['temp_*.csv', 'rh_*.csv', 
                 #'precip_*.csv', 
                 'solrad_*.csv']
    csv_names = ['temp_all.csv', 'rh_all.csv',
                 #'precip_all.csv', 
                 'solrad_all.csv']

    for csvs, csv_name in zip(csv_files, csv_names):
        print(csv_name)
        fnames = glob.glob(os.path.join(basepath, csvs))
        df_all = pd.concat([pd.read_csv(name, index_col=0) for name in fnames])
        df_all.sort_index(axis=1, inplace=True)

        print(df_all.head())
        print(df_all.tail())

#        if os.path.isfile(os.path.join(basepath, csv_name)):
#            print(f'{csv_name} exists already!')
#        else:
#            df_all.to_csv(os.path.join(basepath, csv_name))


def summarize_wea():
    """
    Summarize weather data.

    Parameters
    ----------

    Returns
    -------
    df_wea_summary : pd.DataFrame
        Summary weather data info.

    """
    pass

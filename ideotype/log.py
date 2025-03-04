"""
Generate log file for batch of simulation experiments.

Info include:
- Run setups fetched from setup yaml file.
- ideotype package git hash.

"""
import os
import yaml

from ideotype.data import DATA_PATH


def log_fetchinfo(run_name):
    """
    Fetch info needed for experiment log file.

    Parameters
    ----------
    run_name: str
        Run name for batch of maizsim simulations.
        Must match an existing experiment run name.

    Notes
    _____
    - init_runame.yml info stored in /ideotype/ideotype/data/inits/
    - Each run experiment should have unique init_runame.yml file.

    """
    # setup file name for init_.yml with relative path in data folder
    fpath_init = os.path.join(DATA_PATH, 'inits', 'init_' + run_name + '.yml')

    # check whether specified init_.yml file exist
    if not os.path.isfile(fpath_init):
        raise ValueError(f'init param file {fpath_init} does not exist!')

    # setup log file
    log_runinfo = os.path.join(DATA_PATH, 'logs',
                               'log_' + run_name + '.yml')

    # check if log file for experiment exists already
    if os.path.isfile(log_runinfo):
        raise ValueError(
            f'log file for run_name: "{run_name}" exists already!')

    # read in init param yaml file
    with open(fpath_init, 'r') as pfile:
        dict_init = yaml.safe_load(pfile)

    # check that run name listed in yaml file matches
    # what was passed to log_fetchinfo
    if dict_init['setup']['run_name'] != run_name:
        raise ValueError('mismatched yaml run name!')

    # setup dict to hold all log info
    dict_log = {}

    # fetch all setup info from yaml file and add to log
    for key, value in dict_init['setup'].items():
        dict_log[key] = value

    dict_log['params'] = dict_init['params']
    dict_log['specs'] = dict_init['specs']

    # add yaml file name to log
    dict_log['pdate'] = dict_init['init']['plant_date']
    dict_log['init_yml'] = 'init_' + run_name + '.yml'

    # import package version and add to log
    from ideotype import __version__
    dict_log['ideotype_version'] = __version__

    # writing out log as yaml file
    with open(log_runinfo, 'w') as outfile:
        yaml.dump(dict_log, outfile, default_flow_style=False)

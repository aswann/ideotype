"""Tests for data_process module."""

import os

from ideotype.data_process import read_data, agg_sims
from ideotype import DATA_PATH


def test_read_data():
    """Test read_data."""
    pass


def test_agg_sims():
    """
    Test agg_sims.

    Two testing files to address GitHub file size limit.
    1. Testing on server works with all simulation outputs.
    2. Testing on GitHub repo works with only a portion of the sim outputs.

    """
    if os.path.expanduser('~/') == '/home/disk/eos8/ach315/':
        filepaths_yaml = 'filepaths_local.yml'
    else:
        filepaths_yaml = 'filepaths_repo.yml'

    yamlfile = os.path.join(DATA_PATH, 'files', filepaths_yaml)

    (df_sims, df_sites, df_wea,
     df_params, df_all, df_matured) = read_data(yamlfile)
    df = df_all
    groups = ['cvar', 'site']

    # final aggregated shape
    aggshape = (100, 2)

    # mean
    how = 'mean'
    sim = 'dm_ear'
    mx_mean = agg_sims(df, groups, how, sim)
    assert mx_mean.shape == aggshape

    how = 'variance'
    mx_variance = agg_sims(df, groups, how, sim)
    assert mx_variance.shape == aggshape

    how = 'std'
    mx_std = agg_sims(df, groups, how, sim)
    assert mx_std.shape == aggshape

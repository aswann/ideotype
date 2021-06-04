"""Filter site-years."""

import os
from ideotype.weafile_process import (wea_preprocess,
                                      wea_siteyears,
                                      wea_filter)

# Run name
run_name = 'control_fixpd'

# Paths
basepath = '/home/disk/eos8/ach315/upscale/weadata/process'
outpath = '/home/disk/eos8/ach315/upscale/weadata'

# Preprocess combined weather data
df_temp, df_rh, df_precip, df_solrad = wea_preprocess(basepath)

# Select valid site-years
gseason_start = 2
gseason_end = 11
crthr = 2
siteyears = wea_siteyears(df_temp, df_rh, df_precip, df_solrad,
                          gseason_start, gseason_end, crthr)

# Filter site-years based on area, irrigation, & estimated pdate
area = 10000/2.47  # convert acre into ha
irri = 10
yearspersite = 15
siteyears_filtered = wea_filter(siteyears, area, irri, yearspersite)
siteyears_filtered.to_csv(
    os.path.join(outpath, f'siteyears_{run_name}.csv'), index=False)

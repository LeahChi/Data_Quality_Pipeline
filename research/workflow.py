"""
report.step1() Look at your data (is anything obviously wrong?)
report.step2() Watch out for special values
report.step3() Is any data missing?
report.step4() Check each variable
report.step5() Check combinations of variables
report.step6() Profile the cleaned data

df - dataframe
"""
import os
import pandas as pd
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import datetime

import inspect


from vizdataquality import calculate as vdqc, datasets as vdqd, plot as vdqp, report as vdqr

dataset_filename = 'market_ds.csv'
df = pd.read_csv(dataset_filename, parse_dates=['Date'], dayfirst=True)

# get the dataframe profile
print("shape of dataset (rows,columns)", df.shape)

# profile the dataframe
# this internally computes: missing values, unique vals, outliers etc
df_output = vdqc.calc(df)

# initialise the report
overwrite = False # True or False
report_folder = 'reports' # The folder in which the output is stored (it must exist).

if True:
    report_filename = 'market_stall.html'
    table_kw = {}
else:
    report_filename = 'market_stall.tex'
    mpl.rcParams['savefig.dpi'] = 300 # Save figures at 300 dpi
    table_kw={'position': 'h!'} # Ask Latex to place each image 'exactly here'

#  creating a python object of the report in memory
report = vdqr.Report()
report.add_title("Data quality investigation of a market stalls dataset")

intro = ("This report analyses the data quality of a market stalls dataset."
         "The data is (c) Leeds City Council, 2025, https://datamillnorth.org/dataset/leeds-markets-e519w. This information is licensed under the terms of the Open Government Licence."
         "It applies Roy Ruddle’s six-step workflow to systematically "
         "identify structural issues, missing data, inconsistencies, "
         "and characteristics of the dataset.")
report.add_heading("Introduction", text=intro)


report.add_heading("Workflow Step 1: Look at your data")

# Show first few rows
head_table = df.head()
report.add_table(head_table, caption="First 5 rows of the dataset")

# Show missing & unique counts
missing = df.isna().sum().to_frame("MissingCount")
unique = df.nunique().to_frame("UniqueCount")

report.add_table(missing, caption="Missing values per column")
report.add_table(unique, caption="Unique values per column")

# visual desc
"""
report.add_heading('A section with figures', level=2)
cols = ['Number of missing values', 'Number of unique values']
fig_kw = {'size_inches': (8, 2), 'constrained_layout': True, 'dpi': 300}
ax_kw = {'xlim': (0, num_rows)}
image_filename = os.path.join(report_folder, 'fig_desc_stats.jpg')
vdqp.plotgrid('scalars', df_output[cols], num_cols=2, vert=False, filename=image_filename, overwrite=overwrite, fig_kw=fig_kw, ax_kw=ax_kw)
report.add_figure(image_filename, text='$figure shows other descriptive statistics for each variable.', caption='The number of values and number of unique values in each variable.')
"""

# Visual descriptive statistics
report.add_heading("Workflow Step 1: Descriptive Figures", level=2)

# Combine missing and unique counts into ONE DataFrame (what plotgrid expects)
desc_stats = pd.concat([missing, unique], axis=1)

# Rename columns to match expected interpretation
desc_stats.columns = ["Missing Values", "Unique Values"]

# Figure settings
fig_kw = {'size_inches': (10, 4), 'constrained_layout': True, 'dpi': 300}
ax_kw = {}

# Save figure to the report folder
image_filename = os.path.join(report_folder, "fig_desc_stats.jpg")

# Plot using vdqp.plotgrid
desc_small = desc_stats.head(10)

vdqp.plotgrid(
    "scalars",
    desc_small,
    num_cols=2,
    vert=False,
    filename=image_filename,
    overwrite=True,
    fig_kw={'size_inches': (12,6)},
    ax_kw={}
)


# Add figure to the report
report.add_figure(
    image_filename,
    text="This figure shows missing and unique value counts for each variable.",
    caption="Descriptive statistics: Missing vs Unique values."
)



# Ensure output folder exists
os.makedirs(report_folder, exist_ok=True)

# Full path to file
report_path = os.path.join(report_folder, report_filename)

# Save the report
report.save(report_path)

print("Report saved to:", report_path)
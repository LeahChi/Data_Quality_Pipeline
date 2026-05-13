# Data Quality Profiling Pipeline

A schema-agnostic data quality pipeline for open datasets.
Automatically profiles CSV datasets without prior knowledge of their structure or content.

## What it does
- Classifies columns into three missingness tiers
- Detects sentinel values, category inconsistencies, and constraint violations
- Generates interactive HTML and JSON reports

## Requirements
- Python 3.10+
- pandas, numpy (see requirements.txt)

## Installation
git clone https://github.com/LeahChi/Data_Quality_Pipeline
cd Data_Quality_Pipeline
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

> On Windows activate with: `venv\Scripts\activate`

## Documentation
Full installation and usage instructions are provided in Appendix C of the project report.

## Usage
python3 run_pipeline.py --input data/your_dataset.csv 
                        --name "Your Dataset Name"

## Optional column rules
python3 run_pipeline.py --input data/your_dataset.csv 
                        --name "Dataset Name" 
                        --column-rules "Postcode:valid_postcode"

## Output
Reports saved to outputs/ directory:
- [name]_report.html — interactive report
- [name]_report.json — machine-readable output

## Project structure
See repository for full directory structure.

## Evaluation datasets
See datasets.md for full list of datasets used in evaluation.

## Testing
python3 -m pytest pipeline/tests/test_pipeline.py -v

## Limitations
- CSV format only
- UTF-8 and Latin-1 encoding support
- Single dataset per run
- Chart.js requires internet connection to render

## Academic context
COMP3931 Individual Project — University of Leeds
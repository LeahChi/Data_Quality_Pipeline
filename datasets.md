# Evaluation Datasets

## Core Datasets
| Dataset | Source | Rows | Columns | Notes |
|---------|--------|------|---------|-------|
| Newcastle Library Loans | [URL] | 19 | 205 | Wide time-series |
| Private Water Supplies | [URL] | 16 | 5 | Narrow registry |
| Leeds Market Stalls | [URL] | 9999 | 57 | Large mixed-type |



## Extended Evaluation Datasets
| Dataset | Source | Rows | Columns | Key Finding |
|---------|--------|------|---------|-------------|
| University of Leeds Workforce Diversity | [https://datamillnorth.org/dataset/workforce-diversity-epxnw] | 1 | 35 | 1-row problem. Constant column false positives on single-row aggregated dataset |
| Late Payment Interest 2016-25 (Wakefield Council) | [https://datamillnorth.org/dataset/payment-performance-data-emd3g] | 8 | 9 | Type masquerading — numeric values stored as formatted text (% and comma separators) |
| Bolton Council Expenditure Report | [https://datamillnorth.org/dataset/expenditure-report-2914q] | 2,010 | 6 | Redaction placeholder undetected; field overloading via # delimiter; 333 duplicate rows (16.6%) |
| Yorkshire Water Leakage | [https://datamillnorth.org/dataset/leakage-vqx64] | 2,523 | 18 | integers_only false positives on continuous measurement data; graduated temporal missingness |
| Leeds Trinity University Anchor Diversity Dashboard | [https://datamillnorth.org/dataset/leeds-trinity-university-workforce-diversity-20zwj] | 1 | 66 | 1-row problem confirmed as systemic publishing pattern; zero values indistinguishable from constants |
| Newcastle Listed Buildings | [https://datamillnorth.org/dataset/listed-buildings-2lx98] | 778 | 10 | WKT geometry as opaque text string; fourth distinct cause of structural missingness |
| Fuel Poverty by Region | [https://datamillnorth.org/dataset/fuel-poverty-by-region-england-291xo] | 10 | 4 | Aggregate row mixed with entity rows — mixed granularity invisible to column profiling |
| Leeds City Council Home Adaptations | [https://datamillnorth.org/dataset/home-adaptations-2w30z] | 8,016 | 9 | First validation ERROR — negative ages; em dash as unrecognised missingness marker |
| Leeds EPC Dataset — Geographical Locations | [https://datamillnorth.org/dataset/leeds-epc-geographic-locations-v8d9m] | 178,206 | 5 | Scalability confirmed at 178k rows; OSGB36 coordinate system correctly handled |
| Jobshops Information — Leeds City Council | [https://datamillnorth.org/dataset/jobshops-24zl5] | 43 | 15 | Transposed data structure — pipeline runs correctly on wrong mental model; "?" as undetected uncertainty marker |
| LTH Addresses — Leeds Teaching Hospitals | [https://datamillnorth.org/dataset/hospital-locations-2w3z4] | 7 | 10 | no_negatives false positive on longitude confirmed systematic; telephone area code errors invisible to pipeline |

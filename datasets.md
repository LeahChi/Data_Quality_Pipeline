# Evaluation Datasets

## Core Datasets
| Dataset | Source | Rows | Columns | Notes |
|---------|--------|------|---------|-------|
| Newcastle Library Loans | [https://datamillnorth.org/dataset/newcastle-libraries-loans-e6qw9] | 19 | 205 | Wide time-series |
| Private Water Supplies | [https://datamillnorth.org/dataset/private-water-supplies-e515n] | 16 | 5 | Narrow registry |
| Leeds Market Stalls | [https://datamillnorth.org/dataset/leeds-markets-e519w] | 9999 | 57 | Large mixed-type |



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
| Leeds School Term Dates | [https://datamillnorth.org/dataset/school-term-times-2jqlm] | 346 | 6 | Linked Data URI populated (contrast with Dataset 5); cross-column year mismatch invisible to profiling |
| Leeds Neighbourhood Network Schemes | [https://datamillnorth.org/dataset/neighbourhood-network-schemes-2lq7g] | 34 | 19 | Dual postcode columns by design (LCC schema convention); column name with embedded space |
| Newcastle Libraries Computer Usage | [https://datamillnorth.org/dataset/newcastle-libraries-computer-usage-2lqz5] | 19 | 194 | Percentage strings type-masquerade at scale (176 columns); 198% out-of-range value; inconsistent date column naming convention |
| Leeds Record of Selective Licences | [https://datamillnorth.org/dataset/record-of-selective-licences-for-east-south-and-west-leeds-2k69r] | 102 | 4 | Ltd/Limited/Ltd. abbreviation variants undetected by category consistency; leading whitespace silently inflates unique counts |
| Leeds Council House Rehousing Timescales | [https://datamillnorth.org/dataset/council-house-rehousing-timescales-2kq8r] | 8,500 | 10 | Fractional week values trigger integers_only false positive (8,481 warnings); intra-column year format inconsistency (13/14 vs 15) |
| Leeds Tenants and Residents Groups | [https://datamillnorth.org/dataset/tenancy-and-residents-groups-23yg3] | 148 | 7 | Zero complete columns due to single blank row; embedded newline in cell value; typo in column name |
| Leeds Council House Bids and Lettings | [https://datamillnorth.org/dataset/council-house-bids-and-lettings-e6q49] | 5,900 | 19 | Trailing whitespace in Postcode District values |
| Leeds Domestic Consumption Monitor Monthly Meter Readings | [https://datamillnorth.org/dataset/domestic-consumption-monitor-monthly-meter-readings-e51j7] | 1,000 | 68 | Numeric sentinel 999 detected in property reference column; extreme outlier values |
| Leeds Historic House Prices 1996–2015 | [https://datamillnorth.org/dataset/historic-house-prices-in-leeds-2lqlg] | 273,693 | 15 | UTF-8 encoding failure (latin-1 fallback); missing header row undetected; 11,705 duplicate rows; £-prefixed currency values cause mixed type warning |
| Leeds Community Trigger Indicator for Anti-Social Behaviour | [https://datamillnorth.org/dataset/community-trigger-indicator-for-anti-social-behaviour-2o18n] | 3 | 5 | Transposed summary table — completely clean; integers_only true negative confirms rule works correctly on integer count data |
| Newcastle Scheduled Ancient Monuments | [https://datamillnorth.org/dataset/scheduled-ancient-monumnets-e7lrx] | 72 | 12 | legacyuid column contains two incompatible identifier formats; sub-metre OSGB36 coordinates trigger integers_only false positive |
| Leeds LASSN Grace Hosting | [https://datamillnorth.org/dataset/grace-hosting-ep6og] | 48 | 14 | "na" sentinel marks service maturity phase boundary, not individual missing entries; near-structural blank string columns at 95–98% missing |
| Newcastle Libraries Wi-Fi Users | [https://datamillnorth.org/dataset/newcastle-libraries-wi-fi-users-2lxd3] | 13 | 4 | Fully confirmatory — Walker branch absent across three independent Newcastle datasets; minimal wide time-series handled correctly |
| Leeds Museums and Galleries Events and Exhibitions | [https://datamillnorth.org/dataset/museums-and-galleries-events-and-exhibitions-24z45] | 313 | 10 | Multiline cell values encode multiple audience types invisibly; "free"/"Free"/"FREE" three-variant case inconsistency; 7 category-inconsistent columns |
| Leeds Changing Places Toilets | [https://datamillnorth.org/dataset/changing-places-toilets-in-leeds-24z8n] | 33 | 36 | Dual postcode columns confirm LCC schema convention; opening hours spacing inconsistency undetectable without time format rule; |
| Leeds Safe Places | [https://datamillnorth.org/dataset/safe-places-23yj3] | 201 | 8 | no_negatives false positive on WGS84 longitude; lone quotation mark as cell value |
| Leeds One Stop Centres | [https://datamillnorth.org/dataset/leeds-one-stop-centres-and-joint-service-centres-2y155] | 19 | 89 | 1.0/NaN binary encoding causes 73 no_constant_columns false positives — NaN-as-negative encoding entirely invisible to constant column rule |
| Leeds Lunch Clubs for Over 55s | [https://datamillnorth.org/dataset/lunch-clubs-for-over-55-em75p] | 79 | 10 | Another confirmation of LCC dual postcode schema convention; OSGB36 integer coordinates — integers_only true negative confirmed |
| North Tyneside Pharmacies | [https://datamillnorth.org/dataset/pharmacies-2j756] | 53 | 12 | Blank-string missingness bypasses NaN-based classifier entirely — 71 blank strings, 0 NaN, all columns classified complete; (0,0) coordinate sentinel undetected |
| North Tyneside Doctors, Surgery and Hospital Locations | [https://datamillnorth.org/dataset/doctors-surgery-and-hospital-locations-epxky] | 34 | 13 | Second North Tyneside GIS export confirming blank-string missingness as systematic publisher-level pattern; same schema as pharmacies dataset |
| Harrogate Public Toilets | [https://datamillnorth.org/dataset/harrogate-public-toilets-vdw9o] | 28 | 7 | Blank-string missingness confirmed across third independent publisher; single non-integer OSGB36 value — integers_only potentially actionable rather than purely spurious |
| Leeds Qualified Agency Social Worker Spend | [https://datamillnorth.org/dataset/qualified-agency-social-worker-spend-v8g7q] | 19 | 5 | 52.6% duplicate rate — highest in evaluation set; embedded total row (£41,689.58) confirms mixed granularity pattern for third time |
| Leeds Coronavirus Service Requests | [https://datamillnorth.org/dataset/coronavirus-service-requests-2j73d] | 30,000 | 6 | 15,258 fully blank rows (50.9% of dataset) — largest blank row count in evaluation set; 98,460 total NaN almost entirely explained by blank rows, not substantive missingness |
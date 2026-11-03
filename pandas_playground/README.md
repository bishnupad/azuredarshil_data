# Pandas Dojo

73 pandas drills in 9 levels, from your first Series to multi-step challenges, using the Tokyo 2020 Olympics CSVs in this repo plus two small practice tables.

| Level | Topic | Drills |
|---|---|---|
| 1 | Foundations: Series, DataFrames, shape, columns | 10 |
| 2 | Selecting & filtering: loc, iloc, masks, isin, query | 8 |
| 3 | Sorting & new columns: sort_values, assign, np.where | 7 |
| 4 | Cleaning messy data: strings, to_numeric, to_datetime, NaN, duplicates | 10 |
| 5 | GroupBy & aggregation: agg, named agg, transform, filter | 9 |
| 6 | Merging & joining: concat, merge, indicator, join | 5 |
| 7 | Reshaping: pivot_table, melt, pivot, crosstab, MultiIndex, explode | 7 |
| 8 | Time series: .dt, resample, Grouper, rolling, pct_change | 7 |
| 9 | Pro techniques: cut, qcut, rank, categoricals, pipe, np.select, challenges | 10 |

## Two ways to practise

**In the browser.** The playground page runs real Python (Pyodide) with pandas, checks each answer, and saves your progress on your device.

**In Jupyter.** Open `pandas_dojo.ipynb` from this folder, run the setup cell, then work through the drills. Each drill cell ends with `check('<id>', result)`.

## Files

- `exercises.py`: the drills, hints and reference solutions (one source for both versions)
- `checker.py`: compares your `result` with the reference answer
- `data/`: UTF-8 copies of the Olympics CSVs, plus `sales.csv` and `messy.csv`
- `template.html`, `worker.js`, `runtime.py`, `build.py`: the browser playground
- `test_exercises.py`: confirms every solution passes and every starter fails (`python test_exercises.py`)

Rebuild with `python build.py --pyodide <folder with Pyodide 0.27.7 files> --out dist`.

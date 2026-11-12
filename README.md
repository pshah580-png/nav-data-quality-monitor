# NAV Data Quality Monitor

> **Data note:** Everything in this repository uses **synthetic demo data — created for portfolio demonstration; not employer data.** Funds, NAVs and systems are fictional. Results quoted below are demo-scenario results produced by running the code on that synthetic data — they are not real employer results.

## The business problem

In fund administration, downstream reports are only as good as the daily NAV (Net Asset Value) feed behind them. If a fund's NAV is missing for a business day, duplicated, or stamped with the wrong date, month-end reporting, performance figures and client statements all inherit the error — and the problem is usually found late, by a person, during the busiest week of the month.

This project is a small, runnable version of the control that prevents that: an automated data-quality monitor that checks NAV completeness every day, reconciles the report feed against the source system of record, and repairs the gaps it can prove are safe to repair.

## What it does

1. **Completeness check** — every fund should have one NAV per business day. The monitor compares the report feed to the fund master × business calendar and reports completeness by fund and month.
2. **Duplicate detection** — flags any fund/date reported more than once.
3. **Date-mapping check** — flags NAVs dated on non-business days (a classic symptom of an upstream date-mapping error, e.g. a Friday NAV stamped on Saturday).
4. **Reconciliation fix** — de-duplicates the feed, drops mis-dated rows, and backfills still-missing fund/dates from the source of record using a `UNION` pattern (see `sql/02_reconciliation_and_fix.sql`), then re-measures completeness.

## Demo-scenario result (synthetic data)

Running the pipeline on the synthetic dataset in `data/`:

| Month | Completeness before fix | After reconciliation fix |
|---|---|---|
| 2025-01 | 74.9% | 100% |
| 2025-02 | 80.7% | 100% |
| 2025-03 | 91.3% | 100% |
| 2025-04 | 96.7% | 100% |

The synthetic feed was deliberately built with gaps, ~40 duplicates and weekend-dated rows so the checks have something real to find. Exact figures from your run are written to `output/completeness_report.csv`, with the trend chart in `output/completeness_trend.png`.

## How to run

```bash
pip install -r requirements.txt   # matplotlib only; the rest is stdlib
python python/nav_quality_pipeline.py
```

Outputs land in `output/`: `completeness_report.csv`, `data_quality_summary.txt`, `completeness_trend.png`.

The SQL in `sql/` is the same logic in query form (SQLite / standard SQL) — useful if you want to run the checks directly against a database instead of through the Python pipeline.

## Repository layout

- `data/` — synthetic CSVs: `fund_master.csv` (30 fictional funds), `business_calendar.csv`, `nav_source.csv` (source of record), `nav_reported.csv` (flawed report feed)
- `sql/` — commented validation, reconciliation and fix queries
- `python/` — `nav_quality_pipeline.py`: loads CSVs into SQLite, runs all checks, applies the fix, writes the report + chart
- `output/` — generated report, summary and chart from a demo run

## Skills demonstrated

SQL (joins, `CROSS JOIN` expected-value modelling, `GROUP BY/HAVING` duplicate detection, CTEs, `UNION` backfill, reconciliation) · Python (stdlib `sqlite3`/`csv`, pipeline design) · Data quality & controls (completeness, validity, audit-friendly reporting) · Data visualisation (matplotlib) · Financial-services domain knowledge (NAV, fund reporting, business-day calendars)

## Author

Priyanka Shah — Senior Data / BI Analyst · [Tableau Public](https://public.tableau.com/app/profile/priyanka.shah1267/vizzes) · [GitHub](https://github.com/pshah580-png)

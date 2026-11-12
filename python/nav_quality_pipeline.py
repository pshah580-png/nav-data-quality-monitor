#!/usr/bin/env python3
"""
NAV Data Quality Monitor — runnable pipeline (Python stdlib + matplotlib).

IMPORTANT: All data in ../data is SYNTHETIC demo data — created for
portfolio demonstration; not employer data. Funds are fictional.
Demo-scenario results below are produced by running this code on that
synthetic data; they are not real employer results.

What it does:
  1. Loads the synthetic CSVs into an in-memory SQLite database.
  2. Runs data-quality checks: completeness by month, duplicates,
     non-business-day (date-mapping) anomalies, missing records.
  3. Applies the reconciliation fix from sql/02 (UNION backfill from
     the source of record + de-duplication) and re-measures completeness.
  4. Writes output/completeness_report.csv, output/data_quality_summary.txt
     and output/completeness_trend.png.

Run:  python python/nav_quality_pipeline.py   (from the project folder)
"""
import csv, os, sqlite3, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA, OUT = os.path.join(ROOT, "data"), os.path.join(ROOT, "output")

def load_csv(con, table, filename):
    path = os.path.join(DATA, filename)
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    cols = list(rows[0].keys())
    con.execute(f"CREATE TABLE {table} ({', '.join(c + ' TEXT' for c in cols)})")
    con.executemany(
        f"INSERT INTO {table} VALUES ({', '.join('?' * len(cols))})",
        [tuple(r[c] for c in cols) for r in rows],
    )
    return len(rows)

def pct(reported, expected):
    return round(100.0 * reported / expected, 2) if expected else 0.0

def main():
    os.makedirs(OUT, exist_ok=True)
    con = sqlite3.connect(":memory:")
    n_src = load_csv(con, "nav_source", "nav_source.csv")
    n_rep = load_csv(con, "nav_reported", "nav_reported.csv")
    load_csv(con, "fund_master", "fund_master.csv")
    load_csv(con, "business_calendar", "business_calendar.csv")
    print(f"Loaded: source={n_src} rows, reported={n_rep} rows")

    # --- Check 1: duplicates + date-mapping anomalies -------------------
    dupes = con.execute(
        "SELECT COUNT(*) FROM (SELECT 1 FROM nav_reported "
        "GROUP BY fund_id, nav_date HAVING COUNT(*) > 1)").fetchone()[0]
    weekend = con.execute(
        "SELECT COUNT(*) FROM nav_reported r LEFT JOIN business_calendar c "
        "ON c.business_date = r.nav_date WHERE c.business_date IS NULL"
    ).fetchone()[0]
    print(f"Duplicate fund/date groups found : {dupes}")
    print(f"Non-business-day dated rows found: {weekend}")

    # --- Check 2: completeness BEFORE the fix, by month -----------------
    months = [r[0] for r in con.execute(
        "SELECT DISTINCT month FROM business_calendar ORDER BY month")]
    funds = con.execute("SELECT COUNT(*) FROM fund_master").fetchone()[0]
    before = {}
    for m in months:
        exp = con.execute("SELECT COUNT(*) FROM business_calendar "
                          "WHERE month = ?", (m,)).fetchone()[0] * funds
        got = con.execute(
            "SELECT COUNT(DISTINCT fund_id || '|' || nav_date) FROM nav_reported "
            "WHERE substr(nav_date, 1, 7) = ? AND nav_date IN "
            "(SELECT business_date FROM business_calendar)", (m,)).fetchone()[0]
        before[m] = (got, exp, pct(got, exp))
        print(f"  {m}: reported {got}/{exp} = {before[m][2]}% complete")

    # --- Fix: de-dupe + drop bad dates + UNION backfill from source -----
    con.execute("""
        CREATE TABLE nav_corrected AS
        WITH deduped AS (
            SELECT fund_id, nav_date, MAX(nav_per_share) nav_per_share,
                   MAX(total_net_assets) total_net_assets,
                   MAX(shares_outstanding) shares_outstanding
            FROM nav_reported
            WHERE nav_date IN (SELECT business_date FROM business_calendar)
            GROUP BY fund_id, nav_date)
        SELECT * FROM deduped
        UNION
        SELECT fund_id, nav_date, nav_per_share, total_net_assets,
               shares_outstanding FROM nav_source s
        WHERE NOT EXISTS (SELECT 1 FROM deduped d
                          WHERE d.fund_id = s.fund_id
                            AND d.nav_date = s.nav_date)""")

    # --- Re-measure completeness AFTER the fix ---------------------------
    report_rows = []
    for m in months:
        got, exp, b = before[m][0], before[m][1], before[m][2]
        fixed = con.execute(
            "SELECT COUNT(*) FROM nav_corrected WHERE substr(nav_date,1,7)=?",
            (m,)).fetchone()[0]
        report_rows.append([m, exp, got, b, fixed, pct(fixed, exp)])
        print(f"  {m}: after fix {fixed}/{exp} = {pct(fixed, exp)}% complete")

    with open(os.path.join(OUT, "completeness_report.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["month", "expected_rows", "reported_rows_before_fix",
                    "completeness_before_pct", "rows_after_fix",
                    "completeness_after_pct", "data_note"])
        for r in report_rows:
            w.writerow(r + ["Synthetic demo data - portfolio demonstration"])

    with open(os.path.join(OUT, "data_quality_summary.txt"), "w") as f:
        f.write("NAV Data Quality Monitor - Demo Run Summary\n")
        f.write("Data: SYNTHETIC demo data - not employer data.\n\n")
        f.write(f"Duplicate fund/date groups found : {dupes}\n")
        f.write(f"Non-business-day dated rows found: {weekend}\n")
        for r in report_rows:
            f.write(f"{r[0]}: {r[3]}% complete before fix -> "
                    f"{r[5]}% after reconciliation fix "
                    f"({r[2]} -> {r[4]} of {r[1]} expected rows)\n")
        f.write("\nDemo-scenario result: reconciliation + date-mapping fix "
                "restores the report feed to full completeness on the "
                "synthetic dataset.\n")

    # --- Chart: completeness trend, before vs after ----------------------
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.figure(figsize=(8, 4.2))
        plt.plot(months, [r[3] for r in report_rows], marker="o",
                 label="Report feed (before fix)")
        plt.plot(months, [r[5] for r in report_rows], marker="s",
                 label="After reconciliation fix")
        plt.ylim(60, 105); plt.ylabel("Completeness %")
        plt.title("NAV Completeness by Month — Synthetic Demo Data")
        plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
        plt.savefig(os.path.join(OUT, "completeness_trend.png"), dpi=150)
        print("Chart saved: output/completeness_trend.png")
    except ImportError:
        print("matplotlib not installed — skipping chart (pip install -r requirements.txt)")

    print("Done. Outputs in output/ — completeness_report.csv, "
          "data_quality_summary.txt, completeness_trend.png")
    return 0

if __name__ == "__main__":
    sys.exit(main())

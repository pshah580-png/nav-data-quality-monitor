-- ============================================================
-- NAV Data Quality Monitor — Validation queries (SQLite / standard SQL)
-- Data: SYNTHETIC demo data — created for portfolio demonstration;
--       not employer data. Fictional funds only.
-- Tables (loaded by python/nav_quality_pipeline.py):
--   fund_master(fund_id, fund_name, fund_type, currency, inception_year)
--   business_calendar(business_date, month)
--   nav_source(fund_id, nav_date, nav_per_share, total_net_assets,
--              shares_outstanding, source_system)   -- source system of record
--   nav_reported(...)                               -- downstream report feed
-- ============================================================

-- 1) COMPLETENESS BY FUND AND MONTH
-- Expected = every fund x every business day. Reported is compared to it.
SELECT
    c.month,
    r.fund_id,
    COUNT(DISTINCT c.business_date)              AS expected_days,
    COUNT(DISTINCT r.nav_date)                   AS reported_days,
    ROUND(100.0 * COUNT(DISTINCT r.nav_date)
          / COUNT(DISTINCT c.business_date), 2)  AS completeness_pct
FROM business_calendar c
CROSS JOIN fund_master f
LEFT JOIN nav_reported r
       ON r.fund_id = f.fund_id AND r.nav_date = c.business_date
WHERE r.fund_id = f.fund_id OR r.fund_id IS NULL
GROUP BY c.month, f.fund_id
ORDER BY c.month, completeness_pct;

-- 2) MISSING NAV RECORDS (in calendar + fund list, absent from report feed)
SELECT f.fund_id, c.business_date AS missing_date
FROM business_calendar c
CROSS JOIN fund_master f
LEFT JOIN nav_reported r
       ON r.fund_id = f.fund_id AND r.nav_date = c.business_date
WHERE r.fund_id IS NULL
ORDER BY missing_date, f.fund_id;

-- 3) DUPLICATE DETECTION (same fund + date reported more than once)
SELECT fund_id, nav_date, COUNT(*) AS row_count
FROM nav_reported
GROUP BY fund_id, nav_date
HAVING COUNT(*) > 1
ORDER BY row_count DESC, fund_id;

-- 4) NON-BUSINESS-DAY / DATE-MAPPING ANOMALIES
-- NAVs dated on days that are not business days usually mean an upstream
-- date-mapping error (e.g. Friday NAV stamped on Saturday).
SELECT r.fund_id, r.nav_date
FROM nav_reported r
LEFT JOIN business_calendar c ON c.business_date = r.nav_date
WHERE c.business_date IS NULL
ORDER BY r.nav_date, r.fund_id;

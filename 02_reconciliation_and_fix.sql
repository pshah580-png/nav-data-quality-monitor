-- ============================================================
-- NAV Data Quality Monitor — Reconciliation + fix pattern
-- Data: SYNTHETIC demo data — portfolio demonstration only.
-- Idea: the report feed is reconciled against the source system of
-- record. Gaps in the feed are backfilled from source; duplicates are
-- collapsed; rows already correct in the feed are kept as-is.
-- ============================================================

-- 5) SOURCE-vs-REPORT RECONCILIATION (value differences on matched keys)
SELECT
    s.fund_id, s.nav_date,
    s.nav_per_share  AS source_nav,
    r.nav_per_share  AS reported_nav,
    ROUND(s.nav_per_share - r.nav_per_share, 4) AS difference
FROM nav_source s
JOIN nav_reported r
  ON r.fund_id = s.fund_id AND r.nav_date = s.nav_date
WHERE ABS(s.nav_per_share - r.nav_per_share) > 0.0001
ORDER BY s.nav_date, s.fund_id;

-- 6) THE FIX — build a corrected, de-duplicated reporting table.
-- UNION pattern: take the de-duplicated report feed first, then fill
-- any (fund, business-date) still missing from the source of record.
-- In production this pattern runs as a scheduled reconciliation job;
-- here it is a CREATE TABLE so the before/after report can compare.
DROP TABLE IF EXISTS nav_corrected;
CREATE TABLE nav_corrected AS
WITH deduped_report AS (
    SELECT fund_id, nav_date,
           MAX(nav_per_share)    AS nav_per_share,
           MAX(total_net_assets) AS total_net_assets,
           MAX(shares_outstanding) AS shares_outstanding
    FROM nav_reported
    -- keep only true business days (drops weekend date-mapping errors)
    WHERE nav_date IN (SELECT business_date FROM business_calendar)
    GROUP BY fund_id, nav_date
)
SELECT * FROM deduped_report
UNION
SELECT s.fund_id, s.nav_date, s.nav_per_share,
       s.total_net_assets, s.shares_outstanding
FROM nav_source s
WHERE NOT EXISTS (
    SELECT 1 FROM deduped_report d
    WHERE d.fund_id = s.fund_id AND d.nav_date = s.nav_date
);

-- 7) AFTER-FIX COMPLETENESS (should read 100% for every month)
SELECT
    c.month,
    COUNT(*) AS expected_rows,
    (SELECT COUNT(*) FROM nav_corrected x
      WHERE substr(x.nav_date, 1, 7) = c.month) AS corrected_rows
FROM business_calendar c
GROUP BY c.month
ORDER BY c.month;

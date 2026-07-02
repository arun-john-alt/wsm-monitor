-- Monitor v1 — monthly aggregate at Product × Country × Theme × month.
-- Source: Ads_data_WSM.src_dashboard (perf + impression share, theme-mapped) LEFT JOIN
--         Ads_data_WSM.src_keyword_conversions (conversions, on keyword_id + date).
-- Impression-share rolled up impression-WEIGHTED (non-additive metric → approximate at theme grain).
-- Writes Ads_data_WSM.monitor_monthly. READ-ONLY on the source dataset.
CREATE OR REPLACE TABLE `it-security-online-marketing.Ads_data_WSM.monitor_monthly` AS
WITH conv AS (
  SELECT CAST(campaign_id AS STRING) cid, CAST(ad_group_id AS STRING) agid,
         CAST(ad_group_criterion_criterion_id AS STRING) crit, segments_date d,
         SUM(metrics_conversions) conv, SUM(metrics_conversions_value) conv_val
  FROM `it-security-online-marketing.Ads_data_WSM.src_keyword_conversions`
  GROUP BY 1,2,3,4
),
j AS (
  SELECT d.product, d.campaign_country AS country, d.theme,
         FORMAT_DATE('%Y-%m', d.date) AS ym,
         d.impressions, d.clicks, d.cost,
         d.search_impression_share AS sis, d.search_lost_is_rank AS slir, d.search_abs_top_is AS sabs,
         COALESCE(cv.conv,0) AS conv, COALESCE(cv.conv_val,0) AS conv_val
  FROM `it-security-online-marketing.Ads_data_WSM.src_dashboard` d
  LEFT JOIN conv cv
    ON cv.cid=CAST(d.campaign_id AS STRING) AND cv.agid=CAST(d.ad_group_id AS STRING)
   AND cv.crit=CAST(d.keyword_id AS STRING) AND cv.d=d.date
  WHERE d.product IS NOT NULL AND d.theme IS NOT NULL AND d.campaign_country IS NOT NULL
)
SELECT product, country, theme, ym,
  SUM(impressions) AS impr, SUM(clicks) AS clicks, SUM(cost) AS cost,
  SUM(conv) AS conv, SUM(conv_val) AS conv_val,
  SAFE_DIVIDE(SUM(clicks),SUM(impressions)) AS ctr,
  SAFE_DIVIDE(SUM(cost),SUM(clicks))         AS cpc,
  SAFE_DIVIDE(SUM(cost),SUM(conv))           AS cpa,
  SAFE_DIVIDE(SUM(conv),SUM(clicks))         AS cvr,
  SAFE_DIVIDE(SUM(sis*impressions),SUM(impressions))  AS sis,   -- impression-weighted (approx)
  SAFE_DIVIDE(SUM(slir*impressions),SUM(impressions)) AS slir,
  SAFE_DIVIDE(SUM(sabs*impressions),SUM(impressions)) AS sabs
FROM j
GROUP BY 1,2,3,4

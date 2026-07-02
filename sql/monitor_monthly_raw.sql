-- Monitor option-2 — self-sufficient monthly aggregate from RAW daily Data-Transfer tables
-- (no dependency on Ajay's manual qs_dashboard rebuild → has the current month).
-- Grain Product × Country × Theme × month. Perf from AdGroupBasicStats; IS from AdGroupCrossDeviceStats
-- impression-weighted by SEARCH impressions; theme map via (campaign,ad_group)→themes_firstlast_semroi.
CREATE OR REPLACE TABLE `__W__.monitor_monthly_raw` AS
WITH agmap AS (
  SELECT ad_group_id, ANY_VALUE(ad_group_name) agn FROM `__G__.ads_AdGroup___ACCT__` GROUP BY 1
),
cmap AS (
  SELECT campaign_id, ANY_VALUE(campaign_name) cn FROM `__G__.ads_Campaign___ACCT__` GROUP BY 1
),
tmap AS (
  SELECT LOWER(TRIM(CampaignName)) cn, LOWER(TRIM(AdGroupName)) agn,
         ANY_VALUE(Product) product, ANY_VALUE(Theme) theme, ANY_VALUE(CampaignCountry) country
  FROM `__G__.themes_firstlast_semroi`
  WHERE Theme IS NOT NULL AND CampaignCountry IS NOT NULL AND CampaignName IS NOT NULL AND AdGroupName IS NOT NULL
  GROUP BY 1,2
),
perf AS (   -- ad-group × month: SEARCH-network only (match the keyword-grain dashboard scope)
  SELECT ad_group_id, campaign_id, FORMAT_DATE('%Y-%m', segments_date) ym,
         SUM(metrics_impressions) impr, SUM(metrics_clicks) clicks, SUM(metrics_cost_micros)/1e6 cost
  FROM `__G__.ads_AdGroupBasicStats___ACCT__`
  WHERE segments_date >= '2024-01-01' AND segments_ad_network_type IN ('SEARCH','SEARCH_PARTNERS')
  GROUP BY 1,2,3
),
search_impr AS (  -- search-network impressions per ad_group×date×network (IS weights)
  SELECT ad_group_id, segments_date, segments_ad_network_type, SUM(metrics_impressions) imp
  FROM `__G__.ads_AdGroupBasicStats___ACCT__`
  WHERE segments_date >= '2024-01-01' GROUP BY 1,2,3
),
isag AS (   -- ad-group × month IS, weighted by search impressions
  SELECT x.ad_group_id, FORMAT_DATE('%Y-%m', x.segments_date) ym,
         SUM(x.metrics_search_impression_share * b.imp)            AS w_sis,
         SUM(x.metrics_search_rank_lost_impression_share * b.imp)  AS w_slir,
         SUM(x.metrics_search_absolute_top_impression_share * b.imp) AS w_sabs,
         SUM(b.imp) AS sw
  FROM `__G__.ads_AdGroupCrossDeviceStats___ACCT__` x
  JOIN search_impr b ON b.ad_group_id=x.ad_group_id AND b.segments_date=x.segments_date
       AND b.segments_ad_network_type=x.segments_ad_network_type
  WHERE x.segments_date >= '2024-01-01' AND x.segments_ad_network_type IN ('SEARCH','SEARCH_PARTNERS')
  GROUP BY 1,2
),
ag AS (   -- ad-group × month with theme tag + IS numerator/denominator carried for theme rollup
  SELECT tm.product, tm.country, tm.theme, p.ym, p.impr, p.clicks, p.cost,
         i.w_sis, i.w_slir, i.w_sabs, i.sw
  FROM perf p
  JOIN agmap a ON a.ad_group_id=p.ad_group_id
  JOIN cmap  c ON c.campaign_id=p.campaign_id
  JOIN tmap tm ON tm.cn=LOWER(TRIM(c.cn)) AND tm.agn=LOWER(TRIM(a.agn))
  LEFT JOIN isag i ON i.ad_group_id=p.ad_group_id AND i.ym=p.ym
)
SELECT product, country, theme, ym,
  SUM(impr) impr, SUM(clicks) clicks, SUM(cost) cost,
  SAFE_DIVIDE(SUM(clicks),SUM(impr)) ctr,
  SAFE_DIVIDE(SUM(cost),SUM(clicks)) cpc,
  SAFE_DIVIDE(SUM(w_sis),  SUM(sw)) sis,
  SAFE_DIVIDE(SUM(w_slir), SUM(sw)) slir,
  SAFE_DIVIDE(SUM(w_sabs), SUM(sw)) sabs
FROM ag
GROUP BY 1,2,3,4

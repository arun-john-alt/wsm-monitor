-- monitor_leads_monthly — per Product×Country×Theme×month LEADS + REVENUE, split by engine.
-- __PRESALES__ is substituted from config.yaml (presales_countries) by run_monitor.py.
-- PRESALES markets: FS_PS_Leads/FS_PS_Revenue, Lead_Type='Mktg(SPL)Leads'.
-- ALL OTHER countries: Valid_Sales_Leads_First_Source/FS_Sales_Revenue, single
--   Lead_Type='All Leads' partition (value repeats across the 3 Lead_Types -> one partition avoids 3x).
-- Both First-Source. Engine = Source_Medium. Back to 2024-01 for YoY base.
CREATE OR REPLACE TABLE `__W__.monitor_leads_monthly` AS
WITH presales AS (
  SELECT Product product, CampaignCountry country, Theme theme, SUBSTR(Date,1,7) ym, Source_Medium sm,
         SUM(FS_PS_Leads) leads, SUM(FS_PS_Revenue) revenue
  FROM `__G__.themes_firstlast_semroi`
  WHERE Lead_Type='Mktg(SPL)Leads'
    AND CampaignCountry IN (__PRESALES__)
    AND Product IS NOT NULL AND Theme IS NOT NULL AND CampaignCountry IS NOT NULL AND Date >= '2024-01'
  GROUP BY 1,2,3,4,5
),
sales AS (
  SELECT Product product, CampaignCountry country, Theme theme, SUBSTR(Date,1,7) ym, Source_Medium sm,
         SUM(Valid_Sales_Leads_First_Source) leads, SUM(FS_Sales_Revenue) revenue
  FROM `__G__.themes_firstlast_semroi`
  WHERE Lead_Type='All Leads'
    AND CampaignCountry NOT IN (__PRESALES__)
    AND Product IS NOT NULL AND Theme IS NOT NULL AND CampaignCountry IS NOT NULL AND Date >= '2024-01'
  GROUP BY 1,2,3,4,5
),
u AS (SELECT * FROM presales UNION ALL SELECT * FROM sales)
SELECT product, country, theme, ym,
  SUM(IF(sm='google / cpc', leads, 0))   AS leads_google,
  SUM(IF(sm='bing / cpc',   leads, 0))   AS leads_bing,
  SUM(leads)                             AS leads,        -- consolidated (Google + Bing + unattributed)
  SUM(IF(sm='google / cpc', revenue, 0)) AS rev_google,
  SUM(IF(sm='bing / cpc',   revenue, 0)) AS rev_bing,
  SUM(revenue)                           AS revenue
FROM u
GROUP BY 1,2,3,4

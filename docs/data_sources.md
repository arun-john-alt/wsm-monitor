# BQ Data Sources — Full Reference

Audited: 2026-07-13. All tables in `it-security-online-marketing`.

---

## Datasets

| Dataset | Purpose |
|---|---|
| `Google_ads_data_ajay` | Main source — raw GAds DTS tables + curated views + Ajay's uploads |
| `google_ads_copilot` | Mirror of DTS tables (same account 5419501619) — has `LandingPageStats` + `SearchQueryStats` not in main |
| `Manoj_Google_Ads_Data` | Separate GAds account (1259940298) — different product/geo scope |
| `Ads_data_WSM` | Monitor write dataset (our outputs only) |
| `gsc_data` | Google Search Console — Germany only (`de_stm_search_console`) |
| `US_spend_cut` | City-level spend/revenue views for US |
| `wsm_mkis` | Empty |
| `mahesh_ads_analysis` | Ad-hoc (`admp_uk_search_terms`) |

---

## Key Source Tables

### `themes_firstlast_semroi` — Leads + Revenue Fact Table

Primary grain: `Product × CampaignCountry × Theme × Sub_Theme × AdGroupName × Date`

**Date field semantics (critical):**
- Lead rows → `Date` = lead creation date
- Conversion/revenue rows → `Date` = close date (CRM close date)
- Only 18 rows have both leads + conversions on the same row — they are almost always separate rows

**Source channels:**
- `Source_Medium` — populated for most rows: `'google / cpc'`, `'bing / cpc'`
- `Source___Medium` (triple underscore) — separate column, captures rows where `Source_Medium` is NULL; includes `'chatgptads / cpc'`
- Filter for paid search: `Source_Medium IN ('google / cpc','bing / cpc') OR Source___Medium IN ('google / cpc','bing / cpc','chatgptads / cpc')`
- Row counts: Google 49M, Bing 4.6M, NULL/other 712k (of which ChatGPT ~34k rows)

**Leads — country-dependent metric:**

| Market | Lead field | Lead_Type filter |
|---|---|---|
| US, India, UK, Canada, Australia | `FS_PS_Leads` | `'Mktg(SPL)Leads'` |
| All other countries | `Valid_Sales_Leads_First_Source` | `'All Leads'` (one partition — value repeats across 3 Lead_Types) |

**ROI columns — all 4 time logics:**

| Metric | Presales markets | Sales markets | Date logic |
|---|---|---|---|
| Spend | `Cost` | `Cost` | Spend date |
| Leads | `FS_PS_Leads` | `Valid_Sales_Leads_First_Source` | Lead creation date |
| Conversions | `FS_PS_Conversions` | `FS_Valid_Converted_Leads` | Close date |
| Revenue | `FS_PS_Revenue` | `FS_Sales_Revenue` | Close date |

Last-source variants: `LS_PS_Leads`, `LS_PS_Conversions`, `LS_PS_Revenue`, `LS_Valid_Converted_Leads`, `LS_Sales_Revenue`.

**Ignore:** `FS_conv_from_2022*` / `LS_conv_from_2022*` / `SLFS_*` / `SLLS_*` columns — legacy, not used.

**Revenue coverage note:** Recent months show lower revenue not because of fewer leads but because of the 120-day conversion window — Jan spend generates leads through Apr, those leads close anytime in the future. Always interpret revenue by close-date month, not spend month.

---

### `kw_sv_monthly` — Keyword Search Volume (Monthly)

Grain: `Product × keyword_text × country × campaign_name × ad_group_name × period`

| Field | Notes |
|---|---|
| `search_volume` | Google Keyword Planner bucketed values (480, 590, 720, 1K etc.) — not precise |
| `bid_low`, `bid_high` | Suggested bid range (INR) |
| `platform` | e.g. `'Google Ads'` |
| `period` | Monthly, format `YYYY-MM-01` |

**Coverage:** 6.3M rows, 19,335 keywords, 38 countries, 18 products, Nov 2024 → Apr 2026.

**Refresh:** Manual table by Ajay. Last refreshed Jun 8 2026 (created Jun 3). NOT scheduled — needs manual refresh to get May/Jun 2026 data. Keyword Planner lags ~1–2 months so Apr 2026 was the latest available at time of refresh.

**Dedup note:** Same keyword appears multiple times per month (once per ad group). Use `MAX(search_volume)` or `ANY_VALUE` per keyword × country × period — the SV value is identical across rows for the same keyword+period.

**Also useful:** `qs_dashboard_sv_v` — joins SV onto `qs_trend_cpc_v` (adds `search_volume`, `bid_low`, `bid_high`, `sv_platform` at keyword level).

---

### `ads_LandingPageStats_5419501619` — Landing Page Performance

Location: `google_ads_copilot` dataset (NOT in `Google_ads_data_ajay`).

| Field | Notes |
|---|---|
| `landing_page_view_unexpanded_final_url` | The LP URL |
| `metrics_clicks`, `metrics_impressions`, `metrics_ctr`, `metrics_average_cpc`, `metrics_cost_micros` | Performance |
| `metrics_speed_score` | Page speed score |
| `metrics_mobile_friendly_clicks_percentage` | Mobile friendliness |
| `ad_group_name`, `campaign_name` | Join to theme map via `adgroup_themes` |

**Use for LP cross-country comparison:** For a given theme, find which LP each country uses → compare CTR, CPC, CPL. Join with `themes_firstlast_semroi` via campaign/ad_group → theme → country to add leads and compute CPL per LP. Flag: "Country X uses LP-A (CTR 4%, CPL ₹800) while Country Y uses LP-B (CTR 1.5%, CPL ₹2400) for the same theme."

No campaign_country directly in this table — must join through campaign/ad_group to get country.

---

### `matched_search_terms` — Search Term Performance (Quarterly)

Grain: `Search_Term × Country × Product × Theme × Quarter`

| Field | Notes |
|---|---|
| `Search_Term` | Actual user query |
| `Quarter` | `YYYY-MM-01` (quarter start) |
| `Impressions`, `Clicks`, `Cost` | Performance |
| `Theme`, `Sub_Theme`, `Search_Term_Group` | Classification |
| `Tier_Status` | Term tier (high-value etc.) |
| `Match_Type` | Broad/Phrase/Exact |

**Coverage:** 7.9M rows, 919K unique terms, 16 countries, 12 products, Q1 2025 → Q1 2026.

**Use for search term shift analysis:**
- QoQ term migration — which terms gained/lost clicks per theme/country
- Geo key gaps — terms with strong traffic in one country but zero/low in peer countries (same product)
- Tier migration — terms moving between Tier_Status levels

---

### `ads_SearchQueryStats_5419501619` — Search Query Stats

Location: `google_ads_copilot` dataset.

**NOT a live daily feed** — only 8 distinct days of data (Jun 2024 → Dec 2025, ad-hoc pulls). Use `matched_search_terms` instead for search term analysis.

---

### `qs_dashboard_v_1yr` — Keyword Dashboard (Curated)

Materialized TABLE, ~4.1M rows, keyword × day grain. Pre-joins perf + IS + quality scores.

**Refresh:** Manual by Ajay (`CREATE TABLE AS SELECT`). NOT scheduled. Last rebuild Jun 2 2026 → coverage ends May 31 2026. For current month data, use raw `ads_AdGroup*` tables instead.

Key fields: `final_url` (LP URL), `quality_score`, `lp_experience`, `expected_ctr`, `ad_relevance`, `search_impression_share`, `search_top_is`, `search_abs_top_is`, `search_lost_is_rank`.

`campaign_type` in this table = **match type** (Phrase/Exact/Broad), NOT campaign type (Search/PMax/Display). For real campaign-type segmentation use `ads_Campaign_5419501619`.

---

### `change_events` — Change History

Manual monthly CSV drop by Ajay (lags to ~5th of prior month). Used in RCA only.

---

## Other Notable Tables in `Google_ads_data_ajay`

| Table | What it is |
|---|---|
| `keyword_gap_analysis`, `keyword_gap_analysis_base`, `keyword_gap_analysis_long` | Pre-built geo keyword gap analysis |
| `cross_country_suggestions` | Cross-country keyword suggestions |
| `de_admp_lp_perf` | LP performance for Germany / ADMP (ad-hoc) |
| `ws_country_sv` | Search volume by product × country × theme × keyword |
| `country_keyword_sv` | Keyword SV with MoM%, surging flag, bid |
| `adgroup_themes` | Ad group → theme mapping |
| `kw_theme_mapping` | Keyword → theme mapping |
| `auction_insights_weekly` | EXISTS but EMPTY — auction data is UI-only, not API-available (in talks with Google) |
| `endpoint_central_search_terms` | SV for Endpoint Central only, 2 countries, monthly Nov 2024→May 2026 |

---

## Blocked / Parked

| Item | Status |
|---|---|
| Auction Insights | Table empty — Google standard API doesn't support it; in talks with Google team |
| Bing ad stats | No BQ feed. Options: manual CSV export → BQ, or BQ DTS for Microsoft Ads (needs MS Ads admin) |
| Top-of-page bid estimates | Not in DTS — Keyword Planner API only (not in `ads_KeywordStats`) |
| Campaign type segmentation | `campaign_type` = match type only; need `ads_Campaign` table for Search/PMax/Display split |
| Search volume refresh | `kw_sv_monthly` needs manual refresh by Ajay for May/Jun 2026 |
| ChatGPT ads | In `Source___Medium` (triple underscore) column; ~34k rows; growing channel to watch |

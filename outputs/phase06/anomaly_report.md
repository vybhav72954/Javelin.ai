# JAVELIN.AI - Anomaly Detection Report

*Generated: 2026-01-28 04:01:18*

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Anomalies Detected | 2560 |
| Sites with Anomalies | 1503 |
| Critical Anomalies | 792 |
| High Severity Anomalies | 547 |
| Medium Severity Anomalies | 1221 |

---

## Anomaly Distribution by Type

- **PATTERN_ANOMALY**: 2008 anomalies
- **STATISTICAL_OUTLIER**: 465 anomalies
- **CROSS_STUDY_ANOMALY**: 63 anomalies
- **VELOCITY_ANOMALY**: 21 anomalies
- **REGIONAL_ANOMALY**: 3 anomalies

### Pattern Anomaly Breakdown

- SINGLE_ISSUE_DOMINANCE: 678
- SAE_NOT_FLAGGED: 597
- SAE_WITHOUT_CODING: 351
- STALE_MISSING_DATA: 326
- MAJORITY_HIGH_RISK: 36
- ZERO_ISSUES_HIGH_VOLUME: 20


---

## Top 15 Sites by Anomaly Score

| Rank | Study | Site ID | Country | Score | Anomalies | Critical | High | Types |
|------|-------|---------|---------|-------|-----------|----------|------|-------|
| 1 | Study_22 | Site 543 | - | 1.200 | 2 | 2 | 0 | 2 |
| 2 | Study_11, Study_19 | Site 493 | - | 1.100 | 1 | 1 | 0 | 1 |
| 3 | Study_22 | Site 22 | - | 1.100 | 1 | 1 | 0 | 1 |
| 4 | Study_22 | Site 58 | - | 1.100 | 1 | 1 | 0 | 1 |
| 5 | Study_21 | Site 998 | - | 1.100 | 1 | 1 | 0 | 1 |
| 6 | Study_21 | Site 995 | - | 1.100 | 1 | 1 | 0 | 1 |
| 7 | Study_21 | Site 993 | - | 1.100 | 1 | 1 | 0 | 1 |
| 8 | Study_22 | Site 1704 | - | 1.100 | 1 | 1 | 0 | 1 |
| 9 | Study_21 | Site 988 | - | 1.100 | 1 | 1 | 0 | 1 |
| 10 | Study_21 | Site 982 | - | 1.100 | 1 | 1 | 0 | 1 |
| 11 | Study_21 | Site 975 | - | 1.100 | 1 | 1 | 0 | 1 |
| 12 | Study_21 | Site 972 | - | 1.100 | 1 | 1 | 0 | 1 |
| 13 | Study_21 | Site 965 | - | 1.100 | 1 | 1 | 0 | 1 |
| 14 | Study_21 | Site 963 | - | 1.100 | 1 | 1 | 0 | 1 |
| 15 | Study_21 | Site 957 | - | 1.100 | 1 | 1 | 0 | 1 |


---

## Critical Anomalies (Immediate Action Required)


### 1. Study_1 - Site 27 (CHN)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 6.6σ above average (40 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 2. Study_11 - Site 417 (ITA)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 5.2σ above average (32 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 3. Study_21 - Site 1099 (USA)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 8.0σ above average (48 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 4. Study_21 - Site 1110 (USA)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 6.1σ above average (37 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 5. Study_21 - Site 1180 (USA)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 8.7σ above average (52 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 6. Study_21 - Site 1194 (USA)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 8.2σ above average (49 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 7. Study_21 - Site 1220 (USA)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 8.0σ above average (48 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 8. Study_21 - Site 1389 (COL)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 6.4σ above average (39 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 9. Study_21 - Site 1436 (HUN)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 7.1σ above average (43 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 10. Study_21 - Site 1467 (LTU)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 5.0σ above average (31 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 11. Study_21 - Site 1504 (NZL)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 5.2σ above average (32 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 12. Study_21 - Site 1510 (POL)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 7.3σ above average (44 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 13. Study_21 - Site 1514 (POL)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 7.0σ above average (42 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 14. Study_21 - Site 162 (PRT)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 6.3σ above average (38 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 15. Study_21 - Site 175 (ARG)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 7.1σ above average (43 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 16. Study_21 - Site 22 (USA)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 8.0σ above average (48 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 17. Study_21 - Site 330 (USA)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 5.6σ above average (34 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 18. Study_21 - Site 356 (ARG)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 6.8σ above average (41 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 19. Study_21 - Site 520 (ESP)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 26.0σ above average (152 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 20. Study_21 - Site 916 (ARG)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 6.8σ above average (41 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 21. Study_21 - Site 921 (BRA)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 5.4σ above average (33 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 22. Study_21 - Site 925 (BRA)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 5.9σ above average (36 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 23. Study_21 - Site 950 (BRA)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 6.1σ above average (37 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 24. Study_21 - Site 991 (CHL)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 6.4σ above average (39 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site

### 25. Study_22 - Site 1057 (USA)

- **Type**: STATISTICAL_OUTLIER (Z-Score)
- **Description**: Sae Pending Count is 6.3σ above average (38 vs mean 1.9)
- **Recommendation**: Investigate elevated sae pending count at this site


---

## Regional Anomalies

- **NZL** (ASIA): NZL has 26.9% high-risk subject rate (54/201 subjects)
- **Multiple** (ASIA): ASIA region DQI (0.067) is 1.1σ above other regions
- **Multiple** (Unknown): Unknown region DQI (0.012) is 1.3σ below other regions


---

## Cross-Study Anomalies (Repeat Offender Sites)

- **Site 1018** (USA): Site is high risk in 1/2 studies: Study_24
- **Site 1034** (USA): Site is high risk in 1/2 studies: Study_24
- **Site 1044** (USA): Site is high risk in 1/2 studies: Study_22
- **Site 1059** (USA): Site is high risk in 1/2 studies: Study_21
- **Site 1179** (USA): Site is high risk in 1/2 studies: Study_21
- **Site 1180** (USA): Site is high risk in 1/2 studies: Study_21
- **Site 1184** (USA): Site is high risk in 1/2 studies: Study_22
- **Site 12** (KOR): Site is high risk in 2/5 studies: Study_1, Study_7
- **Site 128** (NLD): Site is high risk in 1/2 studies: Study_11
- **Site 1336** (AUS): Site is high risk in 1/2 studies: Study_21
- **Site 1343** (AUS): Site is high risk in 1/2 studies: Study_22
- **Site 14** (ESP): Site is high risk in 4/10 studies: Study_17, Study_5, Study_6, Study_7
- **Site 155** (GBR): Site is high risk in 2/5 studies: Study_11, Study_19
- **Site 1645** (IND): Site is high risk in 1/2 studies: Study_24
- **Site 1646** (IND): Site is high risk in 1/2 studies: Study_24
- **Site 1648** (IND): Site is high risk in 1/2 studies: Study_24
- **Site 1675** (MYS): Site is high risk in 1/2 studies: Study_24
- **Site 17** (ESP): Site is high risk in 2/4 studies: Study_1, Study_7
- **Site 19** (USA): Site is high risk in 3/5 studies: Study_1, Study_17, Study_5
- **Site 2013** (USA): Site is high risk in 1/2 studies: Study_24
- **Site 2015** (USA): Site is high risk in 1/2 studies: Study_24
- **Site 2030** (USA): Site is high risk in 1/2 studies: Study_24
- **Site 2161** (IND): Site is high risk in 1/2 studies: Study_24
- **Site 2184** (CHN): Site is high risk in 1/2 studies: Study_24
- **Site 2188** (ISR): Site is high risk in 1/2 studies: Study_24
- **Site 259** (IND): Site is high risk in 2/5 studies: Study_24, Study_5
- **Site 27** (CHN): Site is high risk in 1/2 studies: Study_1
- **Site 280** (ESP): Site is high risk in 1/2 studies: Study_5
- **Site 281** (ESP): Site is high risk in 2/3 studies: Study_24, Study_5
- **Site 283** (ESP): Site is high risk in 1/2 studies: Study_5
- **Site 308** (SVK): Site is high risk in 1/2 studies: Study_5
- **Site 309** (SVK): Site is high risk in 1/2 studies: Study_5
- **Site 313** (SVK): Site is high risk in 1/2 studies: Study_5
- **Site 326** (USA): Site is high risk in 2/5 studies: Study_24, Study_5
- **Site 327** (USA): Site is high risk in 3/5 studies: Study_17, Study_24, Study_5
- **Site 328** (USA): Site is high risk in 1/2 studies: Study_5
- **Site 336** (USA): Site is high risk in 1/2 studies: Study_5
- **Site 338** (USA): Site is high risk in 2/2 studies: Study_24, Study_5
- **Site 340** (USA): Site is high risk in 1/2 studies: Study_5
- **Site 341** (USA): Site is high risk in 1/2 studies: Study_21
- **Site 343** (USA): Site is high risk in 1/2 studies: Study_5
- **Site 361** (FRA): Site is high risk in 1/2 studies: Study_8
- **Site 417** (ITA): Site is high risk in 4/8 studies: Study_11, Study_19, Study_20, Study_8
- **Site 425** (CHN): Site is high risk in 2/2 studies: Study_24, Study_8
- **Site 426** (CHN): Site is high risk in 1/2 studies: Study_24
- **Site 444** (ARG): Site is high risk in 1/2 studies: Study_8
- **Site 448** (ARG): Site is high risk in 1/2 studies: Study_8
- **Site 462** (JPN): Site is high risk in 1/2 studies: Study_10
- **Site 476** (DNK): Site is high risk in 1/2 studies: Study_11
- **Site 482** (FRA): Site is high risk in 1/2 studies: Study_11
- **Site 488** (FRA): Site is high risk in 1/2 studies: Study_11
- **Site 493** (DEU): Site is high risk in 2/2 studies: Study_11, Study_19
- **Site 507** (ITA): Site is high risk in 2/4 studies: Study_11, Study_24
- **Site 525** (ARG): Site is high risk in 2/3 studies: Study_11, Study_24
- **Site 6** (AUT): Site is high risk in 2/5 studies: Study_1, Study_24
- **Site 778** (ISR): Site is high risk in 1/2 studies: Study_19
- **Site 834** (ITA): Site is high risk in 1/2 studies: Study_21
- **Site 880** (ESP): Site is high risk in 1/2 studies: Study_24
- **Site 883** (ESP): Site is high risk in 1/2 studies: Study_24
- **Site 884** (ESP): Site is high risk in 1/2 studies: Study_24
- **Site 887** (ESP): Site is high risk in 1/2 studies: Study_24
- **Site 888** (ESP): Site is high risk in 1/2 studies: Study_24
- **Site 953** (CAN): Site is high risk in 1/2 studies: Study_24


---

## Recommendations Summary

Based on the anomaly analysis, key actions:


### CRITICAL Priority

- URGENT: Review site risk classification - pending SAE should trigger High risk
- Investigate elevated lab issues count at this site
- Investigate elevated high risk count at this site
- Investigate elevated sae pending count at this site
- Investigate elevated edrr open issues at this site

### HIGH Priority

- Prioritize NZL for regional training and site support
- Regional strategy review for ASIA
- Site-wide quality intervention needed - majority of subjects have issues
- Critical - single site driving majority of Study_18 data quality issues
- Investigate elevated lab issues count at this site

### MEDIUM Priority

- Investigate elevated lab issues count at this site
- Investigate elevated high risk count at this site
- Regional strategy review for Unknown
- Focus intervention specifically on inactivated forms - appears to be root cause
- High issue concentration - prioritize for intervention


---

*Report generated by JAVELIN.AI Anomaly Detection Engine v2.0*

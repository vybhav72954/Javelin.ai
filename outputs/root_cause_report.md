# JAVELIN.AI - Root Cause Analysis Report

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Sites Analyzed | 100 |
| Systemic Issues Identified | 1 |
| Root Cause Types Found | 5 |
| Prioritized Interventions | 7 |

## Root Cause Distribution

| Root Cause | Sites | % of Analyzed | Classification |
|------------|-------|---------------|----------------|
| STUDY_DESIGN_ISSUE | 94 | 94.0% | SYSTEMIC |
| REGULATORY_COMPLEXITY | 2 | 2.0% | ISOLATED |
| UNKNOWN | 2 | 2.0% | ISOLATED |
| TRAINING_GAP | 1 | 1.0% | ISOLATED |
| PROCESS_BREAKDOWN | 1 | 1.0% | ISOLATED |

## Systemic Issues (Portfolio-Wide)

These issues affect a significant portion of the portfolio and require coordinated intervention:

### STUDY_DESIGN_ISSUE

- **Sites Affected**: 94 (94.0%)
- **Description**: Study-wide pattern suggests protocol or design challenges
- **Recommended Action**: Escalate to study management for protocol review

## Issue Co-occurrence Patterns

Issues that frequently appear together (potential common root causes):

- **Missing Visits** + **Stale Queries (Days)**: 707 sites (lift: 4.74x)
- **Lab Data Issues** + **Stale Missing Pages (Days)**: 135 sites (lift: 4.36x)
- **Uncoded MedDRA Terms** + **Uncoded Drug Terms**: 94 sites (lift: 3.83x)
- **Lab Data Issues** + **Uncoded Drug Terms**: 85 sites (lift: 3.65x)
- **Missing CRF Pages** + **Stale Missing Pages (Days)**: 440 sites (lift: 3.45x)

## Factor Attribution

### Variance Explained by Factor

- **Study**: 136.9% of DQI variance
- **Country**: 12.1% of DQI variance
- **Region**: 4.0% of DQI variance

### Problematic Studies

- **Study_1**: 235.3% higher than average (high-risk rate: 66.7%)
- **Study_13**: 204.9% higher than average (high-risk rate: 15.4%)
- **Study_14**: 230.5% higher than average (high-risk rate: 50.0%)
- **Study_15**: 123.9% higher than average (high-risk rate: 50.0%)
- **Study_16**: 192.4% higher than average (high-risk rate: 56.8%)

## DQI Score Drivers

### By Category

| Category | Sites Affected | % of Portfolio |
|----------|----------------|----------------|
| SAFETY | 1,092 | 32.1% |
| COMPLETENESS | 1,257 | 37.0% |
| TIMELINESS | 984 | 28.9% |
| CODING | 740 | 21.8% |
| ADMINISTRATIVE | 961 | 28.3% |

## Prioritized Interventions

| Intervention | Sites Benefiting | Priority |
|--------------|------------------|----------|
| Escalate to study management for protocol review... | 96 | [!!!] HIGH |
| Schedule targeted training session on identified gap areas... | 86 | [!!!] HIGH |
| Implement enhanced oversight and escalation procedures... | 48 | [!!!] HIGH |
| Engage IT support for system diagnostics... | 11 | [!!] MEDIUM |
| Provide pharmacovigilance support and expedited review... | 2 | [!] LOW |
| Conduct detailed site assessment to identify root cause... | 2 | [!] LOW |
| Review and remediate specific process workflow... | 1 | [!] LOW |

## Top 10 Sites - Root Cause Details

### 1. Study_1 - Site 17 (ESP)

- **DQI Score**: 0.5092
- **Primary Root Cause**: REGULATORY_COMPLEXITY
- **Categories Affected**: SAFETY, COMPLETENESS, TIMELINESS, CODING, ADMINISTRATIVE
- **Top Issues**: Pending SAE Reviews: 8, Uncoded MedDRA Terms: 4, Missing Visits: 2
- **Recommended**: Escalate to study management for protocol review

### 2. Study_24 - Site 558 (TUR)

- **DQI Score**: 0.4606
- **Primary Root Cause**: STUDY_DESIGN_ISSUE
- **Categories Affected**: SAFETY, COMPLETENESS, TIMELINESS, CODING
- **Top Issues**: Uncoded MedDRA Terms: 1, Missing Visits: 1, Missing CRF Pages: 1
- **Recommended**: Escalate to study management for protocol review

### 3. Study_1 - Site 12 (KOR)

- **DQI Score**: 0.4448
- **Primary Root Cause**: STUDY_DESIGN_ISSUE
- **Categories Affected**: COMPLETENESS, TIMELINESS, CODING, ADMINISTRATIVE
- **Top Issues**: Missing Visits: 1, Missing CRF Pages: 2, Lab Data Issues: 4
- **Recommended**: Escalate to study management for protocol review

### 4. Study_24 - Site 524 (ISR)

- **DQI Score**: 0.3945
- **Primary Root Cause**: STUDY_DESIGN_ISSUE
- **Categories Affected**: COMPLETENESS, TIMELINESS, CODING
- **Top Issues**: Missing Visits: 1, Missing CRF Pages: 5, Lab Data Issues: 66
- **Recommended**: Escalate to study management for protocol review

### 5. Study_16 - Site 635 (GRC)

- **DQI Score**: 0.3895
- **Primary Root Cause**: STUDY_DESIGN_ISSUE
- **Categories Affected**: COMPLETENESS, TIMELINESS, CODING, ADMINISTRATIVE
- **Top Issues**: Missing Visits: 2, Missing CRF Pages: 1, Stale Queries (Days): 23
- **Recommended**: Escalate to study management for protocol review

### 6. Study_16 - Site 759 (TUR)

- **DQI Score**: 0.3885
- **Primary Root Cause**: STUDY_DESIGN_ISSUE
- **Categories Affected**: SAFETY, COMPLETENESS, CODING, ADMINISTRATIVE
- **Top Issues**: Pending SAE Reviews: 2, Lab Data Issues: 41, Open EDRR Issues: 8
- **Recommended**: Escalate to study management for protocol review

### 7. Study_24 - Site 1042 (USA)

- **DQI Score**: 0.3855
- **Primary Root Cause**: STUDY_DESIGN_ISSUE
- **Categories Affected**: SAFETY, COMPLETENESS, TIMELINESS
- **Top Issues**: Uncoded MedDRA Terms: 4, Missing CRF Pages: 12, Lab Data Issues: 1
- **Recommended**: Escalate to study management for protocol review

### 8. Study_16 - Site 628 (CAN)

- **DQI Score**: 0.3554
- **Primary Root Cause**: STUDY_DESIGN_ISSUE
- **Categories Affected**: COMPLETENESS, TIMELINESS, CODING, ADMINISTRATIVE
- **Top Issues**: Missing Visits: 3, Lab Data Issues: 18, Stale Queries (Days): 45
- **Recommended**: Escalate to study management for protocol review

### 9. Study_7 - Site 12 (SGP)

- **DQI Score**: 0.351
- **Primary Root Cause**: STUDY_DESIGN_ISSUE
- **Categories Affected**: SAFETY, COMPLETENESS, TIMELINESS, CODING
- **Top Issues**: Uncoded MedDRA Terms: 7, Missing CRF Pages: 25, Stale Missing Pages (Days): 164
- **Recommended**: Escalate to study management for protocol review

### 10. Study_16 - Site 618 (USA)

- **DQI Score**: 0.3458
- **Primary Root Cause**: STUDY_DESIGN_ISSUE
- **Categories Affected**: COMPLETENESS, TIMELINESS, CODING, ADMINISTRATIVE
- **Top Issues**: Missing Visits: 1, Missing CRF Pages: 1, Stale Queries (Days): 8
- **Recommended**: Escalate to study management for protocol review

---

*Report generated by JAVELIN.AI Root Cause Analysis Engine*

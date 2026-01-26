# JAVELIN.AI - Root Cause Analysis Report

*Generated: 2026-01-26 03:47:56*

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Sites Analyzed | 100 |
| Systemic Issues Identified | 1 |
| Root Cause Types Found | 4 |
| Prioritized Interventions | 6 |

## Root Cause Distribution

| Root Cause | Sites | % of Analyzed | Classification |
|------------|-------|---------------|----------------|
| STUDY_DESIGN_ISSUE | 89 | 89.0% | SYSTEMIC |
| REGULATORY_COMPLEXITY | 6 | 6.0% | ISOLATED |
| TRAINING_GAP | 3 | 3.0% | ISOLATED |
| UNKNOWN | 2 | 2.0% | ISOLATED |

## Systemic Issues (Portfolio-Wide)

These issues affect a significant portion of the portfolio and require coordinated intervention:

### STUDY_DESIGN_ISSUE

- **Sites Affected**: 89 (89.0%)
- **Description**: Study-wide pattern suggests protocol or design challenges
- **Recommended Action**: Escalate to study management for protocol review

## Issue Co-occurrence Patterns

Issues that frequently appear together (potential common root causes):

- **Missing Visits** + **Stale Queries (Days)**: 708 sites (lift: 4.77x)
- **Lab Data Issues** + **Stale Missing Pages (Days)**: 142 sites (lift: 4.64x)
- **Uncoded MedDRA Terms** + **Uncoded Drug Terms**: 95 sites (lift: 3.87x)
- **Lab Data Issues** + **Uncoded Drug Terms**: 86 sites (lift: 3.7x)
- **Uncoded MedDRA Terms** + **Lab Data Issues**: 62 sites (lift: 3.5x)

## Factor Attribution

### Variance Explained by Factor

- **Study**: 93.8% of DQI variance
- **Country**: 34.4% of DQI variance
- **Region**: 13.0% of DQI variance

### Problematic Studies

- **Study_1**: 205.9% higher than average (high-risk rate: 24.2%)
- **Study_13**: 152.7% higher than average (high-risk rate: 8.7%)
- **Study_16**: 228.2% higher than average (high-risk rate: 27.1%)
- **Study_17**: 288.1% higher than average (high-risk rate: 18.4%)
- **Study_19**: 334.5% higher than average (high-risk rate: 34.7%)

## DQI Score Drivers

### By Category

| Category | Sites Affected | % of Portfolio |
|----------|----------------|----------------|
| SAFETY | 1,126 | 32.9% |
| COMPLETENESS | 1,490 | 43.5% |
| TIMELINESS | 975 | 28.5% |
| CODING | 741 | 21.6% |
| ADMINISTRATIVE | 963 | 28.1% |

## Prioritized Interventions

| Intervention | Sites Benefiting | Priority |
|--------------|------------------|----------|
| Escalate to study management for protocol review... | 94 | [!!!] HIGH |
| Schedule targeted training session on identified gap areas... | 90 | [!!!] HIGH |
| Implement enhanced oversight and escalation procedures... | 53 | [!!!] HIGH |
| Engage IT support for system diagnostics... | 10 | [!] LOW |
| Provide pharmacovigilance support and expedited review... | 6 | [!] LOW |
| Conduct detailed site assessment to identify root cause... | 2 | [!] LOW |

## Top 10 Sites - Root Cause Details

### 1. Study_1 - Site 17 (ESP)

- **DQI Score**: 0.5164
- **Primary Root Cause**: REGULATORY_COMPLEXITY
- **Categories Affected**: SAFETY, COMPLETENESS, TIMELINESS, CODING, ADMINISTRATIVE
- **Top Issues**: Pending SAE Reviews: 8, Uncoded MedDRA Terms: 4, Missing Visits: 2
- **Recommended**: Escalate to study management for protocol review

### 2. Study_16 - Site 674 (DEU)

- **DQI Score**: 0.4974
- **Primary Root Cause**: REGULATORY_COMPLEXITY
- **Categories Affected**: SAFETY, COMPLETENESS, TIMELINESS, CODING, ADMINISTRATIVE
- **Top Issues**: Pending SAE Reviews: 6, Missing Visits: 5, Missing CRF Pages: 12
- **Recommended**: Escalate to study management for protocol review

### 3. Study_24 - Site 558 (TUR)

- **DQI Score**: 0.4594
- **Primary Root Cause**: STUDY_DESIGN_ISSUE
- **Categories Affected**: SAFETY, COMPLETENESS, TIMELINESS, CODING
- **Top Issues**: Uncoded MedDRA Terms: 1, Missing Visits: 1, Missing CRF Pages: 1
- **Recommended**: Escalate to study management for protocol review

### 4. Study_1 - Site 12 (KOR)

- **DQI Score**: 0.4503
- **Primary Root Cause**: STUDY_DESIGN_ISSUE
- **Categories Affected**: COMPLETENESS, TIMELINESS, CODING, ADMINISTRATIVE
- **Top Issues**: Missing Visits: 1, Missing CRF Pages: 4, Lab Data Issues: 4
- **Recommended**: Escalate to study management for protocol review

### 5. Study_16 - Site 759 (TUR)

- **DQI Score**: 0.4437
- **Primary Root Cause**: STUDY_DESIGN_ISSUE
- **Categories Affected**: SAFETY, COMPLETENESS, CODING, ADMINISTRATIVE
- **Top Issues**: Pending SAE Reviews: 2, Missing CRF Pages: 1, Lab Data Issues: 41
- **Recommended**: Escalate to study management for protocol review

### 6. Study_16 - Site 628 (CAN)

- **DQI Score**: 0.4112
- **Primary Root Cause**: STUDY_DESIGN_ISSUE
- **Categories Affected**: COMPLETENESS, TIMELINESS, CODING, ADMINISTRATIVE
- **Top Issues**: Missing Visits: 3, Missing CRF Pages: 1, Lab Data Issues: 18
- **Recommended**: Escalate to study management for protocol review

### 7. Study_16 - Site 618 (USA)

- **DQI Score**: 0.3901
- **Primary Root Cause**: STUDY_DESIGN_ISSUE
- **Categories Affected**: COMPLETENESS, TIMELINESS, CODING, ADMINISTRATIVE
- **Top Issues**: Missing Visits: 1, Missing CRF Pages: 13, Stale Queries (Days): 8
- **Recommended**: Escalate to study management for protocol review

### 8. Study_24 - Site 524 (ISR)

- **DQI Score**: 0.3882
- **Primary Root Cause**: STUDY_DESIGN_ISSUE
- **Categories Affected**: COMPLETENESS, TIMELINESS, CODING
- **Top Issues**: Missing Visits: 1, Missing CRF Pages: 5, Lab Data Issues: 66
- **Recommended**: Escalate to study management for protocol review

### 9. Study_16 - Site 635 (GRC)

- **DQI Score**: 0.3829
- **Primary Root Cause**: STUDY_DESIGN_ISSUE
- **Categories Affected**: COMPLETENESS, TIMELINESS, CODING, ADMINISTRATIVE
- **Top Issues**: Missing Visits: 2, Missing CRF Pages: 3, Stale Queries (Days): 23
- **Recommended**: Escalate to study management for protocol review

### 10. Study_24 - Site 1042 (USA)

- **DQI Score**: 0.3828
- **Primary Root Cause**: STUDY_DESIGN_ISSUE
- **Categories Affected**: SAFETY, COMPLETENESS, TIMELINESS
- **Top Issues**: Uncoded MedDRA Terms: 4, Missing CRF Pages: 12, Lab Data Issues: 1
- **Recommended**: Escalate to study management for protocol review

---

*Report generated by JAVELIN.AI Root Cause Analysis Engine*

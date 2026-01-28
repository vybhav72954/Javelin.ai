# JAVELIN.AI Site Clustering Analysis Report

**Generated:** 2026-01-28 04:06:16

**Algorithm:** GMM
**Clusters Found:** 10
**Total Sites:** 3424

## Methodology

- **Algorithm:** GMM
- **Type:** Soft clustering (probabilistic assignment)
- **Covariance:** Full covariance matrices
- **Features Used:** 4
  - avg_dqi_score
  - subject_count
  - high_risk_rate
  - issue_rate

## Clustering Quality Metrics

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Silhouette Score | 0.2103 | Fair |
| Calinski-Harabasz | 1052.80 | Higher = better separation |
| Davies-Bouldin | 2.0563 | Poor (lower = better) |

## Cluster Profiles

### Cluster 1: Safety Concerns 🔴

**Sites:** 291 (8.5%)
**Risk Level:** Critical
**Intervention Priority:** 1/5

**Key Metrics:**
- Average DQI Score: 0.0262
- Average Subject Count: 53.3
- High-Risk Rate: 9.9%

**Dominant Issues:**
- SAE Pending (65%)
- Missing Visits (62%)
- Missing Pages (48%)

**Recommended Actions:**
- Immediate SAE review completion
- MedDRA coding backlog clearance
- Safety officer escalation
- Enhanced monitoring protocol

### Cluster 3: Safety Concerns 🔴

**Sites:** 21 (0.6%)
**Risk Level:** Critical
**Intervention Priority:** 1/5

**Key Metrics:**
- Average DQI Score: 0.0314
- Average Subject Count: 176.9
- High-Risk Rate: 12.3%

**Dominant Issues:**
- SAE Pending (81%)
- Open EDRR Issues (48%)
- Missing Visits (43%)

**Recommended Actions:**
- Immediate SAE review completion
- MedDRA coding backlog clearance
- Safety officer escalation
- Enhanced monitoring protocol

### Cluster 7: Safety Concerns 🔴

**Sites:** 156 (4.6%)
**Risk Level:** Critical
**Intervention Priority:** 1/5

**Key Metrics:**
- Average DQI Score: 0.0552
- Average Subject Count: 18.4
- High-Risk Rate: 14.6%

**Dominant Issues:**
- Missing Visits (71%)
- Missing Pages (61%)
- SAE Pending (59%)

**Recommended Actions:**
- Immediate SAE review completion
- MedDRA coding backlog clearance
- Safety officer escalation
- Enhanced monitoring protocol

### Cluster 8: Safety Concerns 🔴

**Sites:** 87 (2.5%)
**Risk Level:** Critical
**Intervention Priority:** 1/5

**Key Metrics:**
- Average DQI Score: 0.1430
- Average Subject Count: 10.1
- High-Risk Rate: 21.6%

**Dominant Issues:**
- Missing Pages (85%)
- Missing Visits (62%)
- Lab Issues (60%)

**Recommended Actions:**
- Immediate SAE review completion
- MedDRA coding backlog clearance
- Safety officer escalation
- Enhanced monitoring protocol

### Cluster 9: Safety Concerns 🔴

**Sites:** 670 (19.6%)
**Risk Level:** Critical
**Intervention Priority:** 1/5

**Key Metrics:**
- Average DQI Score: 0.0420
- Average Subject Count: 19.0
- High-Risk Rate: 18.8%

**Dominant Issues:**
- SAE Pending (92%)
- Missing Pages (12%)
- Missing Visits (11%)

**Recommended Actions:**
- Immediate SAE review completion
- MedDRA coding backlog clearance
- Safety officer escalation
- Enhanced monitoring protocol

### Cluster 0: Data Laggards 🟠

**Sites:** 568 (16.6%)
**Risk Level:** High
**Intervention Priority:** 2/5

**Key Metrics:**
- Average DQI Score: 0.0858
- Average Subject Count: 4.3
- High-Risk Rate: 0.0%

**Dominant Issues:**
- Missing Pages (43%)
- Open EDRR Issues (15%)
- Lab Issues (11%)

**Recommended Actions:**
- Data entry training program
- Weekly compliance check-ins
- CRA monitoring frequency increase
- SDV prioritization

### Cluster 2: Data Laggards 🟠

**Sites:** 225 (6.6%)
**Risk Level:** High
**Intervention Priority:** 2/5

**Key Metrics:**
- Average DQI Score: 0.2203
- Average Subject Count: 4.5
- High-Risk Rate: 36.1%

**Dominant Issues:**
- Missing Pages (97%)
- Missing Visits (62%)
- Lab Issues (45%)

**Recommended Actions:**
- Data entry training program
- Weekly compliance check-ins
- CRA monitoring frequency increase
- SDV prioritization

### Cluster 5: Data Laggards 🟠

**Sites:** 630 (18.4%)
**Risk Level:** High
**Intervention Priority:** 2/5

**Key Metrics:**
- Average DQI Score: 0.0245
- Average Subject Count: 15.4
- High-Risk Rate: 0.0%

**Dominant Issues:**
- Missing Pages (67%)
- Missing Visits (23%)
- Open EDRR Issues (23%)

**Recommended Actions:**
- Data entry training program
- Weekly compliance check-ins
- CRA monitoring frequency increase
- SDV prioritization

### Cluster 6: Moderate Performers 🟢

**Sites:** 40 (1.2%)
**Risk Level:** Low
**Intervention Priority:** 4/5

**Key Metrics:**
- Average DQI Score: 0.0347
- Average Subject Count: 80.6
- High-Risk Rate: 0.2%

**Dominant Issues:**
- Open EDRR Issues (42%)
- Missing Pages (35%)
- Uncoded MedDRA (15%)

**Recommended Actions:**
- Standard monitoring protocol
- Periodic quality reviews

### Cluster 4: High Performers 🟢

**Sites:** 736 (21.5%)
**Risk Level:** Low
**Intervention Priority:** 5/5

**Key Metrics:**
- Average DQI Score: 0.0000
- Average Subject Count: 8.1
- High-Risk Rate: 0.0%

**Recommended Actions:**
- Maintain current practices
- Share best practices with portfolio
- Reduced monitoring frequency eligible


## Cluster Summary Table

| Cluster | Name | Sites | DQI | High-Risk % | Priority |
|---------|------|-------|-----|-------------|----------|
| 1 | Safety Concerns | 291 | 0.0262 | 9.9% | 1 |
| 3 | Safety Concerns | 21 | 0.0314 | 12.3% | 1 |
| 7 | Safety Concerns | 156 | 0.0552 | 14.6% | 1 |
| 8 | Safety Concerns | 87 | 0.1430 | 21.6% | 1 |
| 9 | Safety Concerns | 670 | 0.0420 | 18.8% | 1 |
| 0 | Data Laggards | 568 | 0.0858 | 0.0% | 2 |
| 2 | Data Laggards | 225 | 0.2203 | 36.1% | 2 |
| 5 | Data Laggards | 630 | 0.0245 | 0.0% | 2 |
| 6 | Moderate Performers | 40 | 0.0347 | 0.2% | 4 |
| 4 | High Performers | 736 | 0.0000 | 0.0% | 5 |

## Recommended Intervention Strategy

### Immediate Action Required (Critical)

**Safety Concerns** (291 sites)
- Immediate SAE review completion
- MedDRA coding backlog clearance

**Safety Concerns** (21 sites)
- Immediate SAE review completion
- MedDRA coding backlog clearance

**Safety Concerns** (156 sites)
- Immediate SAE review completion
- MedDRA coding backlog clearance

**Safety Concerns** (87 sites)
- Immediate SAE review completion
- MedDRA coding backlog clearance

**Safety Concerns** (670 sites)
- Immediate SAE review completion
- MedDRA coding backlog clearance

### High Priority (This Week)

**Data Laggards** (568 sites)
- Data entry training program
- Weekly compliance check-ins

**Data Laggards** (225 sites)
- Data entry training program
- Weekly compliance check-ins

**Data Laggards** (630 sites)
- Data entry training program
- Weekly compliance check-ins


---

*Report generated by JAVELIN.AI Site Clustering Module*
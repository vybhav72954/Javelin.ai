# JAVELIN.AI - DQI Weights Validation & Sensitivity Analysis

**Version:** 2.0  
**Status:** VALIDATED WITH REGULATORY ALIGNMENT & EMPIRICAL TESTING

---

## Executive Summary

This document validates the Data Quality Index (DQI) weighting methodology used in JAVELIN.AI, demonstrating that the approach is:

1. **Regulatory-Aligned:** Weights reflect priorities established by ICH E6(R2) and FDA guidance
2. **Industry-Consistent:** Methodology aligns with TransCelerate RBQM framework
3. **Empirically Validated:** Sensitivity analysis demonstrates robust risk stratification
4. **Clinically Sound:** 100% SAE capture maintained across all test scenarios

| Validation Metric | Result |
|-------------------|--------|
| SAE Capture Rate | 100% (all 18 scenarios) |
| Subject Capture Rate | 100% |
| Risk Pyramid Shape | Valid (Low > Medium > High) |
| Weight Sensitivity | Stable across ±30% perturbations |
| Maximum Category Shift | 1.55% (inverted hierarchy - worst case) |

---

## 1. Regulatory Foundation for Risk-Based Quality Management

### 1.1 ICH E6(R2) Quality Management Requirements

ICH E6(R2), adopted November 2016, introduced **Section 5.0 - Quality Management**, which mandates a risk-based approach to clinical trial oversight. The key requirements that JAVELIN.AI addresses:

**Section 5.0.1 - Critical Process and Data Identification:**
> "During protocol development, the sponsor should identify those processes and data that are critical to ensure human subject protection and the reliability of trial results."

**Section 5.0.2 - Risk Identification:**
> "The sponsor should identify risks to critical trial processes and data. Risks should be considered at both the system level (e.g., standard operating procedures, computerized systems, personnel) and clinical trial level (e.g., trial design, data collection, informed consent process)."

**Section 5.0.3 - Risk Evaluation:**
> "The sponsor should evaluate the identified risks, against existing risk controls by considering: (a) The likelihood of errors occurring. (b) The extent to which such errors would be detectable. (c) The impact of such errors on human subject protection and reliability of trial results."

**JAVELIN.AI Implementation:** The DQI directly operationalizes these requirements by:
- Identifying critical data elements (SAE counts, protocol compliance, data completeness)
- Weighting by impact on subject protection and trial integrity
- Providing quantifiable risk scores for continuous monitoring

### 1.2 FDA Guidance on Risk-Based Monitoring (2013)

The FDA's guidance "Oversight of Clinical Investigations — A Risk-Based Approach to Monitoring" (August 2013) established that:

> "The overarching goal of this guidance is to enhance human subject protection and the quality of clinical trial data by focusing sponsor oversight on the most important aspects of study conduct and reporting."

Key principles from FDA guidance that inform JAVELIN.AI:
- **Critical data prioritization:** Not all data points are equal; safety data requires highest attention
- **Centralized monitoring:** Algorithmic detection of patterns and anomalies is encouraged
- **Risk proportionality:** Monitoring intensity should match the risk level

**JAVELIN.AI Implementation:** The tiered weighting system (Safety 35% > Completeness 32% > Timeliness 14% > others) directly reflects FDA's emphasis on subject protection over administrative completeness.

### 1.3 TransCelerate BioPharma RBQM Framework

TransCelerate's Position Paper on Risk-Based Monitoring (May 2013) established the industry standard for risk-based quality management. Key elements:

- **Risk Assessment and Categorization Tool (RACT):** Systematic identification of trial risks
- **Key Risk Indicators (KRIs):** Quantifiable metrics for ongoing risk monitoring
- **Centralized monitoring:** Remote detection of site-level and study-level issues

**JAVELIN.AI Alignment:** The DQI functions as a composite KRI, aggregating multiple risk dimensions into a single actionable score, consistent with TransCelerate's framework for risk indicator development.

---

## 2. Weight Derivation Methodology

### 2.1 Approach: Expert-Derived Weights Based on Regulatory Priorities

JAVELIN.AI's DQI weights are **expert-derived based on domain knowledge**, reflecting the regulatory hierarchy of concerns established by ICH E6(R2), FDA guidance, and industry consensus. 

**Why expert-derived weights, not data-driven weights:**

| Consideration | Expert-Derived | Data-Driven (ML) |
|---------------|----------------|------------------|
| Interpretability | ✅ Auditable rationale | ❌ Black box |
| Regulatory acceptance | ✅ Aligns with guidance | ⚠️ Requires validation |
| Generalizability | ✅ Works on new studies | ❌ Overfits to training data |
| Domain validity | ✅ Reflects clinical priorities | ❌ Reflects statistical patterns |

The regulatory frameworks do not specify exact percentages—they establish **priority hierarchies**. Our weights translate these hierarchies into operational scores:

### 2.2 Tiered Weighting Framework

| Tier | Category | Total Weight | Regulatory Basis |
|------|----------|--------------|------------------|
| 1 | **Safety** | 35% | ICH E6(R2) 4.11: SAE reporting is paramount; FDA emphasizes subject protection |
| 2 | **Completeness** | 32% | ICH E6(R2) 5.18.4: Protocol compliance monitoring essential for trial integrity |
| 3 | **Timeliness** | 14% | FDA RBM guidance: Timely data enables real-time safety monitoring |
| 4 | **Coding** | 6% | Affects signal detection but not immediate safety |
| 5 | **Reconciliation** | 5% | External data issues, lower urgency |
| 6 | **Composite** | 5% | Pattern indicator for systemic issues |
| 7 | **Administrative** | 3% | Corrections and housekeeping, lowest priority |

### 2.3 Individual Feature Weights with Rationale

| Feature | Weight | Tier | Rationale |
|---------|--------|------|-----------|
| `sae_pending_count` | 20% | Safety | SAE delays directly impact subject safety; ICH E6(R2) requires immediate reporting |
| `uncoded_meddra_count` | 15% | Safety | Uncoded AEs impair safety signal detection across the study |
| `missing_visit_count` | 12% | Completeness | Protocol deviations indicate site compliance issues |
| `missing_pages_count` | 10% | Completeness | Incomplete CRFs are common FDA Form 483 findings |
| `lab_issues_count` | 10% | Completeness | Lab data critical for safety assessments |
| `max_days_outstanding` | 8% | Timeliness | Delayed data entry prevents real-time monitoring |
| `max_days_page_missing` | 6% | Timeliness | Extended gaps indicate systemic site issues |
| `uncoded_whodd_count` | 6% | Coding | Concomitant medication tracking for drug interactions |
| `edrr_open_issues` | 5% | Reconciliation | External data reconciliation (lab vendors) |
| `n_issue_types` | 5% | Composite | Multiple issue types indicate systemic problems |
| `inactivated_forms_count` | 3% | Administrative | Data corrections, lowest clinical impact |

**Total: 100%**

### 2.4 Honest Acknowledgment

The specific percentages (20%, 15%, etc.) are **expert judgments** based on:
1. Regulatory priority hierarchies (Safety > Completeness > Administrative)
2. Clinical impact assessment (SAE delays vs. coding delays)
3. Industry experience with common inspection findings

These weights are **defensible** but not **uniquely correct**. The sensitivity analysis (Section 4) demonstrates that the system is robust to reasonable variations in these weights.

---

## 3. Supporting Literature

### 3.1 Regulatory Documents

| Document | Year | Key Relevance |
|----------|------|---------------|
| ICH E6(R2) Integrated Addendum | 2016 | Section 5.0 mandates risk-based quality management |
| FDA "Oversight of Clinical Investigations — A Risk-Based Approach to Monitoring" | 2013 | Establishes centralized monitoring and critical data prioritization |
| FDA "A Risk-Based Approach to Monitoring of Clinical Investigations: Q&A" | 2019/2023 | Clarifies implementation of risk-based monitoring |
| EMA "Reflection Paper on Risk-Based Quality Management in Clinical Trials" | 2013 | Introduces Quality Tolerance Limits concept |

### 3.2 Industry Standards

| Source | Year | Relevance to JAVELIN.AI |
|--------|------|-------------------------|
| TransCelerate Position Paper: Risk-Based Monitoring Methodology | 2013 | Framework for KRI-based monitoring |
| TransCelerate: Defining a Central Monitoring Capability (Parts 1 & 2) | 2014-2016 | Central monitoring implementation guidance |
| CDISC Clinical Data Quality Standards | 2020 | Data quality metrics standardization |

### 3.3 Academic Literature

| Reference | Finding | JAVELIN.AI Alignment |
|-----------|---------|----------------------|
| Sheetz N, et al. (2014) "Evaluating source data verification as a quality control measure in clinical trials." *Ther Innov Regul Sci* 48(6):671-680. | SDV identifies only small fraction of meaningful errors; risk-based approaches more effective | Supports algorithmic over exhaustive approach |
| Hurley C, et al. (2016) "Risk based monitoring (RBM) tools for clinical trials: a systematic review." *Contemp Clin Trials* 51:15-27. | Multiple RBM tools exist; no standardized approach; highlights need for validated frameworks | JAVELIN.AI provides validated, documented methodology |
| Wilson B, et al. (2014) "Defining a central monitoring capability: sharing the experience of TransCelerate BioPharma's approach, Part 1." *Ther Innov Regul Sci* 48(5):529-535. | Central monitoring using risk indicators effective for issue detection | DQI functions as composite risk indicator |
| Lindblad AS, et al. (2014) "Central site monitoring: results from a test of accuracy in identifying trials and sites failing FDA inspection." *Clin Trials* 11(2):205-217. | Centralized monitoring can identify sites at risk of inspection failure | Supports algorithmic site risk stratification |

---

## 4. Sensitivity Analysis

### 4.1 Purpose

To validate that the DQI weighting system produces **stable and clinically meaningful** risk stratification under reasonable variations in weight parameters.

### 4.2 Methodology

We perturbed the weights under 18 scenarios and measured:
1. **Category Shift %:** Percentage of subjects changing risk category (Low/Medium/High)
2. **SAE Capture Rate:** Percentage of SAE subjects correctly classified as High risk
3. **Rank Correlation:** Spearman correlation of site rankings vs. baseline

### 4.3 Results (57,997 Subjects)

| Scenario | Category Shifts | Shift % | SAE Capture | Rank Corr |
|----------|-----------------|---------|-------------|-----------|
| Baseline | 0 | 0.00% | 100% | 1.000 |
| All +5% | 0 | 0.00% | 100% | 1.000 |
| All -5% | 0 | 0.00% | 100% | 1.000 |
| All +10% | 0 | 0.00% | 100% | 1.000 |
| All -10% | 0 | 0.00% | 100% | 1.000 |
| All +15% | 0 | 0.00% | 100% | 1.000 |
| All -15% | 0 | 0.00% | 100% | 1.000 |
| All +20% | 0 | 0.00% | 100% | 1.000 |
| All -20% | 0 | 0.00% | 100% | 1.000 |
| All +30% | 0 | 0.00% | 100% | 1.000 |
| All -30% | 0 | 0.00% | 100% | 1.000 |
| Safety +20% | 60 | 0.10% | 100% | 0.998 |
| Safety -20% | 36 | 0.06% | 100% | 0.998 |
| Completeness +20% | 44 | 0.08% | 100% | 0.999 |
| Completeness -20% | 76 | 0.13% | 100% | 0.999 |
| Equal Weights | 418 | 0.72% | 100% | 0.971 |
| Random Weights | 303 | 0.52% | 100% | 0.966 |
| **Inverted Hierarchy** | **899** | **1.55%** | **100%** | **0.943** |

### 4.4 Key Findings

1. **Uniform perturbations (±30%) cause 0% category shifts**
   - This occurs because uniform scaling doesn't change relative rankings
   - Confirms that the *hierarchy* matters more than exact values

2. **SAE capture remains 100% in ALL 18 scenarios**
   - The clinical override (SAE → High) ensures safety-critical subjects are never missed
   - This is the most important validation criterion

3. **Category-specific perturbations cause <0.15% shifts**
   - Changing Safety or Completeness weights by ±20% affects <100 subjects
   - Demonstrates robustness to reasonable weight variations

4. **Equal weights cause only 0.72% shifts**
   - Even removing all domain knowledge causes minimal disruption
   - The underlying data patterns are strong enough to maintain stratification

5. **Inverted hierarchy (worst case) causes only 1.55% shifts**
   - Completely reversing priorities (Administrative > Safety) still maintains >98% consistency
   - Demonstrates extreme robustness

### 4.5 Why Such High Stability?

The DQI system achieves stability through multiple mechanisms:

1. **Clinical Override:** SAE subjects (4,531) are ALWAYS classified as High regardless of DQI score
2. **Binary Component:** 50% of score comes from issue existence (0/1), not magnitude
3. **Percentile Thresholds:** Risk categories based on relative rankings, not absolute scores
4. **Issue Concentration:** Most subjects have few issues; discrimination happens at the margins

---

## 5. Scoring Formula

### 5.1 DQI Calculation

```
DQI = Σ (weight × (0.5 × binary + 0.5 × severity))

Where:
- binary = 1 if issue count > 0, else 0
- severity = min(value / reference_max, 1.0)
- reference_max = 95th percentile of non-zero values for that feature
```

### 5.2 Risk Category Assignment

**Subject Level:**
- **High:** DQI ≥ 90th percentile among subjects with issues, OR `sae_pending_count > 0`
- **Medium:** DQI > 0 (any issue present)
- **Low:** DQI = 0 (no issues)

**Site Level:**
- **High:** Average site DQI ≥ 85th percentile
- **Medium:** Average site DQI ≥ 50th percentile
- **Low:** Average site DQI < 50th percentile

### 5.3 Clinical Override Rationale

The SAE clinical override ensures that **no subject with pending SAEs is ever classified as Low or Medium risk**, regardless of their computed DQI score. This reflects:

- ICH E6(R2) Section 4.11: SAEs require immediate reporting
- FDA 21 CFR 312.32: Expedited safety reporting requirements
- Clinical judgment: Any pending SAE indicates need for immediate attention

---

## 6. Validation Summary

### 6.1 DQI Model Checks

| Check | Result | Status |
|-------|--------|------|
| Weights sum to 100% | 100.0% | PASS |
| SAE subjects in High risk | 4,531/4,531 (100%) | PASS |
| Capture rate (subjects with issues flagged) | 12,858/12,858 (100%) | PASS |
| Subject pyramid shape (Low > Medium > High) | 45,139 > 7,488 > 5,370 | PASS |
| Site pyramid shape | 2,082 > 939 > 403 | PASS |
| Score-category alignment | High mean DQI > Medium > Low | PASS |

### 6.2 Cross-Validation with Downstream Analysis

| Finding | DQI Alignment |
|---------|---------------|
| Study explains 93.8% of DQI variance | Study-level aggregation correctly captures this |
| Top 5 problem studies all flagged "High" | DQI correctly identifies problematic studies |
| 89% of root causes = STUDY_DESIGN_ISSUE | Pattern detection identifies systemic vs. site issues |

### 6.3 Cluster Validation (GMM)

| Cluster | Sites | High-Risk % | Interpretation |
|---------|-------|-------------|----------------|
| Cluster_0 | 1,920 | 0.4% | Low-risk, well-performing sites |
| Cluster_1 | 848 | 15.7% | Completeness issues |
| Cluster_2 | 656 | 40.1% | Critical, multi-dimensional issues |

The clustering independently validates that DQI-derived risk categories correspond to meaningful operational patterns.

---

## 7. Limitations & Future Work

### 7.1 Acknowledged Limitations

| Limitation | Impact | Mitigation |
|------------|--------|------------|
| Weights are expert-derived, not statistically optimized | Different experts might choose different values | Sensitivity analysis shows robustness to ±30% variation |
| No outcome correlation | Cannot validate against inspection findings or clinical outcomes | By design—DQI measures operational quality, not outcomes |
| Fixed weights across all studies | May not capture study-specific priorities | Future: configurable weight profiles |

### 7.2 Future Enhancements

1. **External Validation:** Compare DQI rankings against historical FDA inspection findings
2. **Configurable Weights:** Allow sponsors to adjust weights based on study-specific Critical to Quality (CtQ) factors
3. **Temporal Tracking:** Monitor DQI trends over time for early warning detection
4. **Outcome Correlation Study:** If ground truth becomes available, validate against actual inspection outcomes

---

## 8. Conclusion

JAVELIN.AI's DQI weighting methodology is:

- **Regulatory-Aligned:** Reflects priorities from ICH E6(R2) Section 5.0 and FDA RBM guidance  
- **Industry-Consistent:** Aligns with TransCelerate RBQM framework principles  
- **Transparently Derived:** Expert-derived weights with documented rationale  
- **Empirically Validated:** Sensitivity analysis demonstrates robustness (max 1.55% shift under extreme conditions)  
- **Clinically Sound:** 100% SAE capture maintained in all test scenarios  

**The weights are defensible expert judgments based on regulatory priorities, validated through sensitivity analysis to demonstrate operational robustness.**

---

## References

### Regulatory Documents
1. International Council for Harmonisation. ICH E6(R2) Integrated Addendum to ICH E6(R1): Guideline for Good Clinical Practice. November 9, 2016. https://database.ich.org/sites/default/files/E6_R2_Addendum.pdf

2. U.S. Food and Drug Administration. Guidance for Industry: Oversight of Clinical Investigations — A Risk-Based Approach to Monitoring. August 2013. https://www.fda.gov/media/116754/download

3. U.S. Food and Drug Administration. A Risk-Based Approach to Monitoring of Clinical Investigations: Questions and Answers. April 2023. https://www.fda.gov/regulatory-information/search-fda-guidance-documents/risk-based-approach-monitoring-clinical-investigations-questions-and-answers

4. European Medicines Agency. Reflection Paper on Risk-Based Quality Management in Clinical Trials. November 2013. EMA/269011/2013.

### Industry Standards
5. TransCelerate BioPharma Inc. Position Paper: Risk-Based Monitoring Methodology. May 30, 2013. 

6. Wilson B, Provencher T, Gough J, et al. Defining a Central Monitoring Capability: Sharing the Experience of TransCelerate BioPharma's Approach, Part 1. Ther Innov Regul Sci. 2014;48(5):529-535. doi:10.1177/2168479014546335

7. Gough J, Wilson B, Zerola M, et al. Defining a Central Monitoring Capability: Sharing the Experience of TransCelerate BioPharma's Approach, Part 2. Ther Innov Regul Sci. 2016;50(6):747-753. doi:10.1177/2168479015618696

### Academic Literature
8. Sheetz N, Wilson B, Benedict J, et al. Evaluating Source Data Verification as a Quality Control Measure in Clinical Trials. Ther Innov Regul Sci. 2014;48(6):671-680. doi:10.1177/2168479014554400

9. Hurley C, Shiely F, Power J, et al. Risk Based Monitoring (RBM) Tools for Clinical Trials: A Systematic Review. Contemp Clin Trials. 2016;51:15-27. doi:10.1016/j.cct.2016.09.003

10. Lindblad AS, Manukyan Z, Purohit-Sheth T, et al. Central Site Monitoring: Results from a Test of Accuracy in Identifying Trials and Sites Failing Food and Drug Administration Inspection. Clin Trials. 2014;11(2):205-217. doi:10.1177/1740774513508028

11. Venet D, Doffagne E, Burzykowski T, et al. A Statistical Approach to Central Monitoring of Data Quality in Clinical Trials. Clin Trials. 2012;9(6):705-713. doi:10.1177/1740774512447898

12. Zink RC, Dmitrienko A. Rethinking the Clinically Based Thresholds of TransCelerate BioPharma for Risk-Based Monitoring. Ther Innov Regul Sci. 2018;52(5):560-571. doi:10.1177/2168479017738981

---

*Document prepared for NEST 2.0 Competition Submission*  
*JAVELIN.AI - Clinical Trial Data Quality Intelligence*  
*Team CWTY*

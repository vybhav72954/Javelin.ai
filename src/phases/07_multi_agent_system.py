"""
Javelin.AI - Phase 07: Multi-Agent Analysis System
==============================================================

Implements a multi-agent system where specialized AI agents analyze clinical
trial sites from different perspectives and coordinate to produce prioritized
recommendations.

Prerequisites:
    - Run 03_calculate_dqi.py (Phase 03)
    - Run 06_anomaly_detection.py (Phase 06)
    - outputs/phase03/master_site_with_dqi.csv must exist
    - outputs/phase06/site_anomaly_scores.csv must exist

Usage:
    python src/phases/07_multi_agent_system.py
    python src/phases/07_multi_agent_system.py --model mistral --top-sites 100
    python src/phases/07_multi_agent_system.py --fast

CLI Options:
    --model         Ollama model to use (default: mistral)
    --top-sites     Number of top sites to analyze (default: 50)
    --fast          Skip LLM, use rule-based analysis only

Output:
    - outputs/phase07/multi_agent_recommendations.csv   # Final recommendations
    - outputs/phase07/agent_analysis.json               # Detailed agent outputs
    - outputs/phase07/multi_agent_report.md             # Human-readable report

Agent Architecture:
    - Safety Agent (40%): SAE, MedDRA, regulatory compliance
    - Data Quality Agent (35%): Missing data, timeliness
    - Performance Agent (25%): Benchmarking, trends
    - Coordinator Agent: Synthesizes insights, resolves conflicts


    ┌─────────────────────────────────────────────────────────────┐
    │                    COORDINATOR AGENT                        │
    │         (Synthesizes insights, resolves conflicts)          │
    └─────────────────────────────────────────────────────────────┘
                              ▲
          ┌───────────────────┼───────────────────┐
          │                   │                   │
    ┌─────┴─────┐       ┌─────┴─────┐       ┌─────┴─────┐
    │  SAFETY   │       │   DATA    │       │PERFORMANCE│
    │   AGENT   │       │  QUALITY  │       │   AGENT   │
    │           │       │   AGENT   │       │           │
    │ - SAE     │       │ - Missing │       │ - Bench-  │
    │ - MedDRA  │       │   data    │       │   marking │
    │ - Regul.  │       │ - Stale   │       │ - Trends  │
    └───────────┘       └───────────┘       └───────────┘
"""

import sys
import json
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
import warnings

warnings.filterwarnings('ignore')

import sys
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ============================================================================
# PATH SETUP
# ============================================================================

_SCRIPT_DIR = Path(__file__).parent.resolve()
_SRC_DIR = _SCRIPT_DIR.parent if _SCRIPT_DIR.name == 'phases' else _SCRIPT_DIR
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

# ============================================================================
# CONFIGURATION - With PHASE_DIRS Integration
# ============================================================================

try:
    from config import PROJECT_ROOT, OUTPUT_DIR, PHASE_DIRS
    _USING_CONFIG = True
except ImportError:
    _USING_CONFIG = False
    PROJECT_ROOT = _SRC_DIR.parent
    OUTPUT_DIR = PROJECT_ROOT / "outputs"
    PHASE_DIRS = {f'phase_{i:02d}': OUTPUT_DIR for i in range(10)}

# Phase-specific directories
PHASE_03_DIR = PHASE_DIRS.get('phase_03', OUTPUT_DIR)
PHASE_06_DIR = PHASE_DIRS.get('phase_06', OUTPUT_DIR)
PHASE_07_DIR = PHASE_DIRS.get('phase_07', OUTPUT_DIR)

# Input paths (from Phase 03 and 06)
SITE_DQI_PATH = PHASE_03_DIR / "master_site_with_dqi.csv"
SUBJECT_DQI_PATH = PHASE_03_DIR / "master_subject_with_dqi.csv"
STUDY_DQI_PATH = PHASE_03_DIR / "master_study_with_dqi.csv"
REGION_DQI_PATH = PHASE_03_DIR / "master_region_with_dqi.csv"
COUNTRY_DQI_PATH = PHASE_03_DIR / "master_country_with_dqi.csv"
ANOMALIES_PATH = PHASE_06_DIR / "anomalies_detected.csv"
SITE_ANOMALY_SCORES_PATH = PHASE_06_DIR / "site_anomaly_scores.csv"

# Output paths (to Phase 07)
RECOMMENDATIONS_PATH = PHASE_07_DIR / "multi_agent_recommendations.csv"
AGENT_ANALYSIS_PATH = PHASE_07_DIR / "agent_analysis.json"
REPORT_PATH = PHASE_07_DIR / "multi_agent_report.md"

# Configuration
TOP_SITES_TO_ANALYZE = 50
AGENT_TIMEOUT = 30


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class AgentAnalysis:
    """Structured output from an agent's analysis."""
    agent_name: str
    site_id: str
    study: str
    risk_level: str  # Critical, High, Medium, Low
    confidence: float  # 0-1
    findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""


@dataclass
class SiteRecommendation:
    """Final coordinated recommendation for a site."""
    site_id: str
    study: str
    priority: int  # 1 = highest
    risk_category: str
    composite_score: float
    safety_score: float
    quality_score: float
    performance_score: float
    top_issues: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    agent_consensus: str = ""
    escalation_required: bool = False


# ============================================================================
# LLM INTEGRATION (Optional - Ollama)
# ============================================================================

class OllamaLLM:
    """Simple Ollama integration for local LLM inference."""

    def __init__(self, model: str = "mistral", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if Ollama is running."""
        try:
            import urllib.request
            req = urllib.request.Request(f"{self.base_url}/api/tags")
            with urllib.request.urlopen(req, timeout=2) as response:
                return response.status == 200
        except Exception:
            return False

    def generate(self, prompt: str, system: str = None) -> str:
        """Generate response from LLM."""
        if not self.available:
            return ""
        try:
            import urllib.request
            import json as json_lib
            data = {"model": self.model, "prompt": prompt, "stream": False}
            if system:
                data["system"] = system
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=json_lib.dumps(data).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=AGENT_TIMEOUT) as response:
                result = json_lib.loads(response.read().decode('utf-8'))
                return result.get('response', '')
        except Exception as e:
            print(f"    [WARN] LLM call failed: {e}")
            return ""


# ============================================================================
# BASE AGENT CLASS
# ============================================================================

class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(self, name: str, llm: Optional[OllamaLLM] = None):
        self.name = name
        self.llm = llm
        self.weight = 1.0

    @abstractmethod
    def analyze(self, site_data: Dict, context: Dict) -> AgentAnalysis:
        """Analyze a site and return findings."""
        pass

    def _calculate_risk_level(self, score: float) -> str:
        """Convert numeric score to risk level."""
        if score >= 0.8:
            return "Critical"
        elif score >= 0.6:
            return "High"
        elif score >= 0.4:
            return "Medium"
        else:
            return "Low"

    def _llm_enhance(self, analysis: AgentAnalysis, prompt: str) -> AgentAnalysis:
        """Optionally enhance analysis with LLM reasoning."""
        if self.llm and self.llm.available:
            system = f"You are a {self.name} analyzing clinical trial data quality."
            response = self.llm.generate(prompt, system)
            if response:
                analysis.reasoning = response[:500]
        return analysis


# ============================================================================
# SAFETY AGENT
# ============================================================================

class SafetyAgent(BaseAgent):
    """
    Focuses on patient safety indicators:
    - SAE (Serious Adverse Event) pending reviews
    - MedDRA coding completeness
    - Regulatory compliance signals
    """

    def __init__(self, llm: Optional[OllamaLLM] = None):
        super().__init__("SafetyAgent", llm)
        self.weight = 0.40  # Safety is highest priority

    def analyze(self, site_data: Dict, context: Dict) -> AgentAnalysis:
        """Analyze safety-related metrics for a site."""
        site_id = site_data.get('site_id', 'Unknown')
        study = site_data.get('study', 'Unknown')

        findings = []
        recommendations = []
        metrics = {}

        # SAE Analysis
        sae_pending = site_data.get('sae_pending_count_sum', 0)
        sae_total = site_data.get('sae_total_count_sum', 0)
        metrics['sae_pending'] = sae_pending
        metrics['sae_total'] = sae_total

        if sae_pending > 0:
            findings.append(f"CRITICAL: {sae_pending} SAE reviews pending")
            recommendations.append("Immediate SAE review completion required")
            if sae_pending >= 5:
                recommendations.append("Escalate to Safety Officer")

        # MedDRA Coding
        uncoded_meddra = site_data.get('uncoded_meddra_count_sum', 0)
        metrics['uncoded_meddra'] = uncoded_meddra

        if uncoded_meddra > 0:
            findings.append(f"Uncoded adverse events: {uncoded_meddra}")
            recommendations.append("Complete MedDRA coding for adverse events")

        # WHODD Coding (drug terms)
        uncoded_whodd = site_data.get('uncoded_whodd_count_sum', 0)
        metrics['uncoded_whodd'] = uncoded_whodd

        if uncoded_whodd > 0:
            findings.append(f"Uncoded drug terms: {uncoded_whodd}")
            recommendations.append("Complete WHODD coding for medications")

        # Calculate safety score
        safety_score = 0.0
        if sae_pending > 0:
            safety_score += min(0.5, sae_pending * 0.1)
        if uncoded_meddra > 0:
            safety_score += min(0.3, uncoded_meddra * 0.05)
        if uncoded_whodd > 0:
            safety_score += min(0.2, uncoded_whodd * 0.02)
        safety_score = min(1.0, safety_score)
        metrics['safety_score'] = safety_score

        # Risk assessment
        risk_level = self._calculate_risk_level(safety_score)
        confidence = 0.9 if sae_pending > 0 else 0.7

        # Portfolio comparison
        portfolio_avg_sae = context.get('portfolio_avg_sae', 0)
        if sae_pending > portfolio_avg_sae * 2 and portfolio_avg_sae > 0:
            findings.append(f"SAE rate {sae_pending/max(portfolio_avg_sae,0.1):.1f}x portfolio average")

        analysis = AgentAnalysis(
            agent_name=self.name,
            site_id=site_id,
            study=study,
            risk_level=risk_level,
            confidence=confidence,
            findings=findings,
            recommendations=recommendations,
            metrics=metrics
        )

        # LLM enhancement
        if findings:
            prompt = f"Site {site_id} has {sae_pending} pending SAE reviews, {uncoded_meddra} uncoded adverse events. What's the regulatory risk?"
            analysis = self._llm_enhance(analysis, prompt)

        return analysis


# ============================================================================
# DATA QUALITY AGENT
# ============================================================================

class DataQualityAgent(BaseAgent):
    """
    Focuses on data completeness and timeliness:
    - Missing visits
    - Missing CRF pages
    - Stale/outstanding queries
    - Lab data issues
    """

    def __init__(self, llm: Optional[OllamaLLM] = None):
        super().__init__("DataQualityAgent", llm)
        self.weight = 0.35

    def analyze(self, site_data: Dict, context: Dict) -> AgentAnalysis:
        """Analyze data quality metrics for a site."""
        site_id = site_data.get('site_id', 'Unknown')
        study = site_data.get('study', 'Unknown')

        findings = []
        recommendations = []
        metrics = {}

        # Missing Visits
        missing_visits = site_data.get('missing_visit_count_sum', 0)
        metrics['missing_visits'] = missing_visits

        if missing_visits > 0:
            findings.append(f"Missing visits: {missing_visits}")
            if missing_visits >= 10:
                recommendations.append("Urgent: Complete visit documentation")
            else:
                recommendations.append("Schedule visit data entry")

        # Missing Pages
        missing_pages = site_data.get('missing_pages_count_sum', 0)
        max_days_missing = site_data.get('max_days_page_missing_sum', 0)
        metrics['missing_pages'] = missing_pages
        metrics['max_days_page_missing'] = max_days_missing

        if missing_pages > 0:
            findings.append(f"Missing CRF pages: {missing_pages}")
            if max_days_missing > 30:
                findings.append(f"Pages missing for {max_days_missing} days")
                recommendations.append("URGENT: Address long-outstanding missing pages")

        # Lab Issues
        lab_issues = site_data.get('lab_issues_count_sum', 0)
        metrics['lab_issues'] = lab_issues

        if lab_issues > 0:
            findings.append(f"Lab data issues: {lab_issues}")
            recommendations.append("Review and resolve lab data discrepancies")

        # EDRR Open Issues
        edrr_issues = site_data.get('edrr_open_issues_sum', 0)
        metrics['edrr_issues'] = edrr_issues

        if edrr_issues > 0:
            findings.append(f"Open reconciliation issues: {edrr_issues}")
            recommendations.append("Complete external data reconciliation")

        # Inactivated Forms (lower priority)
        inactivated = site_data.get('inactivated_forms_count_sum', 0)
        metrics['inactivated_forms'] = inactivated

        if inactivated > 5:
            findings.append(f"Inactivated forms: {inactivated}")
            recommendations.append("Review form inactivation patterns")

        # Calculate quality score
        quality_score = 0.0
        subject_count = max(site_data.get('subject_count', 1), 1)

        if missing_visits > 0:
            quality_score += min(0.3, (missing_visits / subject_count) * 0.5)
        if missing_pages > 0:
            quality_score += min(0.3, (missing_pages / subject_count) * 0.3)
        if lab_issues > 0:
            quality_score += min(0.2, (lab_issues / subject_count) * 0.3)
        if edrr_issues > 0:
            quality_score += min(0.1, (edrr_issues / subject_count) * 0.2)
        if max_days_missing > 30:
            quality_score += 0.1
        quality_score = min(1.0, quality_score)
        metrics['quality_score'] = quality_score

        # DQI from pipeline
        dqi_score = site_data.get('avg_dqi_score', 0)
        metrics['dqi_score'] = dqi_score

        risk_level = self._calculate_risk_level(quality_score)
        confidence = 0.85

        analysis = AgentAnalysis(
            agent_name=self.name,
            site_id=site_id,
            study=study,
            risk_level=risk_level,
            confidence=confidence,
            findings=findings,
            recommendations=recommendations,
            metrics=metrics
        )

        if findings:
            prompt = f"Site {site_id} has {missing_visits} missing visits, {missing_pages} missing pages, {lab_issues} lab issues. Summarize data quality concerns."
            analysis = self._llm_enhance(analysis, prompt)

        return analysis


# ============================================================================
# PERFORMANCE AGENT
# ============================================================================

class PerformanceAgent(BaseAgent):
    """
    Focuses on site performance and benchmarking:
    - Cross-study comparison
    - Trend analysis
    - Portfolio-level patterns
    """

    def __init__(self, llm: Optional[OllamaLLM] = None):
        super().__init__("PerformanceAgent", llm)
        self.weight = 0.25

    def analyze(self, site_data: Dict, context: Dict) -> AgentAnalysis:
        """Analyze performance metrics for a site."""
        site_id = site_data.get('site_id', 'Unknown')
        study = site_data.get('study', 'Unknown')

        findings = []
        recommendations = []
        metrics = {}

        # Get site metrics
        subject_count = site_data.get('subject_count', 0)
        high_risk_count = site_data.get('high_risk_count', 0)
        avg_dqi = site_data.get('avg_dqi_score', 0)
        site_risk = site_data.get('site_risk_category', 'Unknown')
        metrics['subject_count'] = subject_count
        metrics['high_risk_count'] = high_risk_count
        metrics['avg_dqi'] = avg_dqi
        metrics['site_risk_category'] = site_risk

        # Portfolio comparison
        portfolio_avg_dqi = context.get('portfolio_avg_dqi', 0)
        portfolio_avg_subjects = context.get('portfolio_avg_subjects', 0)

        if portfolio_avg_dqi > 0 and avg_dqi > portfolio_avg_dqi * 1.5:
            findings.append(f"DQI {avg_dqi:.3f} is {avg_dqi/portfolio_avg_dqi:.1f}x portfolio average")
            recommendations.append("Investigate systemic issues at site")

        # High risk rate
        high_risk_rate = high_risk_count / max(subject_count, 1)
        metrics['high_risk_rate'] = high_risk_rate

        portfolio_avg_high_risk_rate = context.get('portfolio_avg_high_risk_rate', 0)
        if high_risk_rate > 0.2:
            findings.append(f"High-risk subject rate: {high_risk_rate*100:.1f}%")
            if high_risk_rate > portfolio_avg_high_risk_rate * 2 and portfolio_avg_high_risk_rate > 0:
                findings.append("Rate significantly exceeds portfolio average")
                recommendations.append("Root cause analysis recommended")

        # Study context
        study_risk = context.get('study_risks', {}).get(study, 'Unknown')
        metrics['study_risk_category'] = study_risk

        if study_risk == 'High' and site_risk == 'High':
            findings.append(f"Both site and study ({study}) are high-risk")
            recommendations.append("Coordinate with study team on remediation")

        # Regional context
        country = site_data.get('country', 'Unknown')
        region = site_data.get('region', 'Unknown')
        country_risk = context.get('country_risks', {}).get(country, 'Unknown')
        region_risk = context.get('region_risks', {}).get(region, 'Unknown')
        metrics['country'] = country
        metrics['region'] = region
        metrics['country_risk'] = country_risk
        metrics['region_risk'] = region_risk

        if country_risk == 'High':
            findings.append(f"Located in high-risk country: {country}")

        # Anomaly status
        is_anomaly = site_data.get('is_anomaly', False)
        anomaly_score = site_data.get('anomaly_score', 0)
        metrics['is_anomaly'] = is_anomaly
        metrics['anomaly_score'] = anomaly_score

        if is_anomaly:
            findings.append(f"Flagged as statistical anomaly (score: {anomaly_score:.2f})")
            recommendations.append("Review anomaly detection findings")

        # Calculate performance score
        perf_score = 0.0
        if avg_dqi > 0:
            perf_score += min(0.4, avg_dqi)
        if high_risk_rate > 0.1:
            perf_score += min(0.3, high_risk_rate)
        if is_anomaly:
            perf_score += 0.2
        if site_risk == 'High':
            perf_score += 0.1
        perf_score = min(1.0, perf_score)
        metrics['performance_score'] = perf_score

        risk_level = self._calculate_risk_level(perf_score)
        confidence = 0.75

        analysis = AgentAnalysis(
            agent_name=self.name,
            site_id=site_id,
            study=study,
            risk_level=risk_level,
            confidence=confidence,
            findings=findings,
            recommendations=recommendations,
            metrics=metrics
        )

        if findings:
            prompt = f"Site {site_id} in {country} has DQI {avg_dqi:.3f}, {high_risk_rate*100:.1f}% high-risk subjects. What patterns suggest?"
            analysis = self._llm_enhance(analysis, prompt)

        return analysis


# ============================================================================
# COORDINATOR AGENT
# ============================================================================

class CoordinatorAgent(BaseAgent):
    """
    Synthesizes analyses from all agents:
    - Resolves conflicts
    - Prioritizes findings
    - Produces final recommendations
    """

    def __init__(self, llm: Optional[OllamaLLM] = None):
        super().__init__("CoordinatorAgent", llm)

    def synthesize(self, analyses: List[AgentAnalysis], site_data: Dict) -> SiteRecommendation:
        """Synthesize multiple agent analyses into a final recommendation."""
        site_id = site_data.get('site_id', 'Unknown')
        study = site_data.get('study', 'Unknown')

        # Collect all findings and recommendations
        all_findings = []
        all_recommendations = []
        risk_levels = []

        safety_score = 0.0
        quality_score = 0.0
        performance_score = 0.0

        for analysis in analyses:
            all_findings.extend(analysis.findings)
            all_recommendations.extend(analysis.recommendations)
            risk_levels.append(analysis.risk_level)

            if analysis.agent_name == "SafetyAgent":
                safety_score = analysis.metrics.get('safety_score', 0)
            elif analysis.agent_name == "DataQualityAgent":
                quality_score = analysis.metrics.get('quality_score', 0)
            elif analysis.agent_name == "PerformanceAgent":
                performance_score = analysis.metrics.get('performance_score', 0)

        # Determine overall risk (most severe wins)
        risk_priority = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}
        sorted_risks = sorted(risk_levels, key=lambda x: risk_priority.get(x, 4))
        overall_risk = sorted_risks[0] if sorted_risks else "Low"

        # Calculate composite score (weighted)
        composite_score = (
            safety_score * 0.40 +
            quality_score * 0.35 +
            performance_score * 0.25
        )

        # Determine if escalation required
        escalation_required = (
            overall_risk == "Critical" or
            safety_score >= 0.7 or
            (overall_risk == "High" and safety_score >= 0.5)
        )

        # Deduplicate and prioritize recommendations
        unique_recs = list(dict.fromkeys(all_recommendations))
        # Prioritize safety-related recommendations
        safety_keywords = ['SAE', 'safety', 'urgent', 'immediate', 'escalate', 'MedDRA']
        prioritized_recs = sorted(
            unique_recs,
            key=lambda r: (0 if any(kw.lower() in r.lower() for kw in safety_keywords) else 1)
        )

        # Build consensus statement
        consensus_parts = []
        if safety_score > 0.5:
            consensus_parts.append("Safety concerns require immediate attention")
        if quality_score > 0.5:
            consensus_parts.append("Data quality issues affecting reliability")
        if performance_score > 0.5:
            consensus_parts.append("Performance below portfolio standards")

        if not consensus_parts:
            consensus_parts.append("Site within acceptable parameters")

        consensus = ". ".join(consensus_parts) + "."

        # Calculate priority (1 = highest)
        if overall_risk == "Critical":
            priority = 1
        elif overall_risk == "High" and safety_score >= 0.5:
            priority = 2
        elif overall_risk == "High":
            priority = 3
        elif overall_risk == "Medium":
            priority = 4
        else:
            priority = 5

        return SiteRecommendation(
            site_id=site_id,
            study=study,
            priority=priority,
            risk_category=overall_risk,
            composite_score=round(composite_score, 4),
            safety_score=round(safety_score, 4),
            quality_score=round(quality_score, 4),
            performance_score=round(performance_score, 4),
            top_issues=all_findings[:5],
            recommended_actions=prioritized_recs[:5],
            agent_consensus=consensus,
            escalation_required=escalation_required
        )

    def analyze(self, site_data: Dict, context: Dict) -> AgentAnalysis:
        """Not used directly - use synthesize() instead."""
        return AgentAnalysis(
            agent_name=self.name,
            site_id=site_data.get('site_id', 'Unknown'),
            study=site_data.get('study', 'Unknown'),
            risk_level="Low",
            confidence=0.0
        )


# ============================================================================
# MULTI-AGENT SYSTEM
# ============================================================================

class MultiAgentSystem:
    """Orchestrates multiple agents for comprehensive site analysis."""

    def __init__(self, llm: Optional[OllamaLLM] = None):
        self.llm = llm
        self.safety_agent = SafetyAgent(llm)
        self.quality_agent = DataQualityAgent(llm)
        self.performance_agent = PerformanceAgent(llm)
        self.coordinator = CoordinatorAgent(llm)
        self.portfolio_context = {}

    def set_portfolio_context(self, site_df: pd.DataFrame, study_df: pd.DataFrame = None,
                              region_df: pd.DataFrame = None, country_df: pd.DataFrame = None):
        """Set portfolio-level context for comparative analysis."""
        self.portfolio_context = {
            'portfolio_avg_dqi': site_df['avg_dqi_score'].mean() if 'avg_dqi_score' in site_df else 0,
            'portfolio_avg_subjects': site_df['subject_count'].mean() if 'subject_count' in site_df else 0,
            'portfolio_avg_sae': site_df['sae_pending_count_sum'].mean() if 'sae_pending_count_sum' in site_df else 0,
            'portfolio_avg_high_risk_rate': (site_df['high_risk_count'].sum() / max(site_df['subject_count'].sum(), 1)) if 'high_risk_count' in site_df else 0,
            'total_sites': len(site_df),
            'total_studies': site_df['study'].nunique() if 'study' in site_df else 0,
        }

        # Study risk lookup
        if study_df is not None and 'study_risk_category' in study_df.columns:
            self.portfolio_context['study_risks'] = dict(zip(study_df['study'], study_df['study_risk_category']))
        else:
            self.portfolio_context['study_risks'] = {}

        # Region risk lookup
        if region_df is not None and 'region_risk_category' in region_df.columns:
            self.portfolio_context['region_risks'] = dict(zip(region_df['region'], region_df['region_risk_category']))
        else:
            self.portfolio_context['region_risks'] = {}

        # Country risk lookup
        if country_df is not None and 'country_risk_category' in country_df.columns:
            self.portfolio_context['country_risks'] = dict(zip(country_df['country'], country_df['country_risk_category']))
        else:
            self.portfolio_context['country_risks'] = {}

    def analyze_site(self, site_data: Dict) -> tuple:
        """Run all agents on a single site and return coordinated results."""
        analyses = []

        # Run each specialized agent
        safety_analysis = self.safety_agent.analyze(site_data, self.portfolio_context)
        analyses.append(safety_analysis)

        quality_analysis = self.quality_agent.analyze(site_data, self.portfolio_context)
        analyses.append(quality_analysis)

        performance_analysis = self.performance_agent.analyze(site_data, self.portfolio_context)
        analyses.append(performance_analysis)

        # Coordinator synthesizes
        recommendation = self.coordinator.synthesize(analyses, site_data)

        return recommendation, analyses


# ============================================================================
# REPORT GENERATION
# ============================================================================

def generate_report(recommendations: List[SiteRecommendation],
                    all_analyses: Dict[str, List[AgentAnalysis]],
                    portfolio_stats: Dict) -> str:
    """Generate markdown report."""
    lines = []
    lines.append("# JAVELIN.AI Multi-Agent Analysis Report")
    lines.append(f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"\n**Sites Analyzed:** {len(recommendations)}")

    # Agent Architecture
    lines.append("\n## Agent Architecture\n")
    lines.append("```")
    lines.append("┌─────────────────────────────────────────────────────────────┐")
    lines.append("│                    COORDINATOR AGENT                         │")
    lines.append("│         (Synthesizes insights, resolves conflicts)           │")
    lines.append("└─────────────────────────────────────────────────────────────┘")
    lines.append("                              ▲")
    lines.append("          ┌───────────────────┼───────────────────┐")
    lines.append("          │                   │                   │")
    lines.append("    ┌─────┴─────┐       ┌─────┴─────┐       ┌─────┴─────┐")
    lines.append("    │  SAFETY   │       │   DATA    │       │PERFORMANCE│")
    lines.append("    │   AGENT   │       │  QUALITY  │       │   AGENT   │")
    lines.append("    │   (40%)   │       │   (35%)   │       │   (25%)   │")
    lines.append("    └───────────┘       └───────────┘       └───────────┘")
    lines.append("```")

    # Executive Summary
    lines.append("\n## Executive Summary\n")
    critical_count = sum(1 for r in recommendations if r.risk_category == "Critical")
    high_count = sum(1 for r in recommendations if r.risk_category == "High")
    medium_count = sum(1 for r in recommendations if r.risk_category == "Medium")
    escalation_count = sum(1 for r in recommendations if r.escalation_required)

    lines.append(f"- **Critical Risk Sites:** {critical_count}")
    lines.append(f"- **High Risk Sites:** {high_count}")
    lines.append(f"- **Medium Risk Sites:** {medium_count}")
    lines.append(f"- **Escalations Required:** {escalation_count}")

    # Portfolio Context
    lines.append("\n## Portfolio Context\n")
    lines.append(f"- Total Sites in Portfolio: {portfolio_stats.get('total_sites', 'N/A')}")
    lines.append(f"- Total Studies: {portfolio_stats.get('total_studies', 'N/A')}")
    lines.append(f"- Portfolio Avg DQI: {portfolio_stats.get('portfolio_avg_dqi', 0):.4f}")
    lines.append(f"- Portfolio Avg SAE Pending: {portfolio_stats.get('portfolio_avg_sae', 0):.2f}")

    # Critical Priority Sites
    critical_recs = [r for r in recommendations if r.priority <= 2]
    if critical_recs:
        lines.append("\n## Critical Priority Sites (Immediate Action Required)\n")
        for rec in sorted(critical_recs, key=lambda x: x.priority)[:10]:
            lines.append(f"### Site: {rec.site_id} ({rec.study})")
            lines.append(f"- **Risk Category:** {rec.risk_category}")
            lines.append(f"- **Composite Score:** {rec.composite_score:.4f}")
            lines.append(f"- **Escalation Required:** {'YES' if rec.escalation_required else 'No'}")
            lines.append(f"- **Consensus:** {rec.agent_consensus}")
            if rec.top_issues:
                lines.append("- **Key Issues:**")
                for issue in rec.top_issues[:3]:
                    lines.append(f"  - {issue}")
            if rec.recommended_actions:
                lines.append("- **Recommended Actions:**")
                for action in rec.recommended_actions[:3]:
                    lines.append(f"  - {action}")
            lines.append("")

    # High Priority Sites
    high_recs = [r for r in recommendations if r.priority == 3]
    if high_recs:
        lines.append("\n## High Priority Sites\n")
        lines.append("| Site | Study | Composite | Safety | Quality | Performance |")
        lines.append("|------|-------|-----------|--------|---------|-------------|")
        for rec in sorted(high_recs, key=lambda x: -x.composite_score)[:15]:
            lines.append(f"| {rec.site_id} | {rec.study} | {rec.composite_score:.3f} | {rec.safety_score:.3f} | {rec.quality_score:.3f} | {rec.performance_score:.3f} |")

    # Action Summary by Domain
    lines.append("\n## Action Summary by Domain\n")

    # Safety actions
    safety_actions = []
    for rec in recommendations:
        for action in rec.recommended_actions:
            if any(kw in action.lower() for kw in ['sae', 'safety', 'meddra', 'adverse']):
                safety_actions.append(action)
    if safety_actions:
        lines.append("### Safety Domain")
        for action in list(dict.fromkeys(safety_actions))[:5]:
            lines.append(f"- {action}")

    # Quality actions
    quality_actions = []
    for rec in recommendations:
        for action in rec.recommended_actions:
            if any(kw in action.lower() for kw in ['visit', 'page', 'lab', 'data', 'missing']):
                quality_actions.append(action)
    if quality_actions:
        lines.append("\n### Data Quality Domain")
        for action in list(dict.fromkeys(quality_actions))[:5]:
            lines.append(f"- {action}")

    lines.append("\n---")
    lines.append(f"\n*Report generated by JAVELIN.AI Multi-Agent System*")

    return "\n".join(lines)


# ============================================================================
# MAIN PIPELINE
# ============================================================================

def run_multi_agent_analysis(model: str = "mistral", top_sites: int = TOP_SITES_TO_ANALYZE, use_llm: bool = True):
    """Main function to run multi-agent analysis."""
    print("=" * 70)
    print("JAVELIN.AI - MULTI-AGENT ANALYSIS SYSTEM")
    print("=" * 70)

    if _USING_CONFIG:
        print("(Using centralized config with PHASE_DIRS)")
    print(f"\nInput Directory (Phase 03): {PHASE_03_DIR}")
    print(f"Input Directory (Phase 06): {PHASE_06_DIR}")
    print(f"Output Directory (Phase 07): {PHASE_07_DIR}")

    # Initialize LLM
    llm = None
    if use_llm:
        print(f"\nInitializing LLM (model: {model})...")
        llm = OllamaLLM(model=model)
        if llm.available:
            print("  [OK] LLM available")
        else:
            print("  [WARN] LLM not available, using rule-based analysis only")
    else:
        print("\nSkipping LLM (--fast mode)")

    # Initialize multi-agent system
    mas = MultiAgentSystem(llm)

    # Load data
    print("\n" + "=" * 70)
    print("STEP 1: LOAD DATA")
    print("=" * 70)

    if not SITE_DQI_PATH.exists():
        print(f"\n[ERROR] Site DQI file not found: {SITE_DQI_PATH}")
        print("Please run Phase 03 first.")
        return False

    site_df = pd.read_csv(SITE_DQI_PATH)
    print(f"  [OK] Loaded {len(site_df):,} sites")

    # Load optional files
    study_df = pd.read_csv(STUDY_DQI_PATH) if STUDY_DQI_PATH.exists() else None
    region_df = pd.read_csv(REGION_DQI_PATH) if REGION_DQI_PATH.exists() else None
    country_df = pd.read_csv(COUNTRY_DQI_PATH) if COUNTRY_DQI_PATH.exists() else None

    if study_df is not None:
        print(f"  [OK] Loaded {len(study_df)} studies")
    if region_df is not None:
        print(f"  [OK] Loaded {len(region_df)} regions")
    if country_df is not None:
        print(f"  [OK] Loaded {len(country_df)} countries")

    # Load anomalies if available
    anomalies_df = None
    if SITE_ANOMALY_SCORES_PATH.exists():
        anomalies_df = pd.read_csv(SITE_ANOMALY_SCORES_PATH)
        print(f"  [OK] Loaded anomaly scores for {len(anomalies_df)} sites")

    # Enrich site data with anomaly info
    if anomalies_df is not None:
        site_df = site_df.merge(
            anomalies_df[['study', 'site_id', 'anomaly_score', 'is_anomaly']],
            on=['study', 'site_id'],
            how='left'
        )
        site_df['anomaly_score'] = site_df['anomaly_score'].fillna(0)
        site_df['is_anomaly'] = site_df['is_anomaly'].fillna(False)

    # Set portfolio context
    print("\n" + "=" * 70)
    print("STEP 2: SET PORTFOLIO CONTEXT")
    print("=" * 70)

    mas.set_portfolio_context(site_df, study_df, region_df, country_df)
    print(f"  Portfolio Avg DQI: {mas.portfolio_context['portfolio_avg_dqi']:.4f}")
    print(f"  Portfolio Avg SAE: {mas.portfolio_context['portfolio_avg_sae']:.2f}")
    print(f"  Total Sites: {mas.portfolio_context['total_sites']}")
    print(f"  Total Studies: {mas.portfolio_context['total_studies']}")

    # Select top sites for analysis
    print("\n" + "=" * 70)
    print(f"STEP 3: SELECT TOP {top_sites} SITES FOR ANALYSIS")
    print("=" * 70)

    # Composite ranking
    site_df['_rank_score'] = 0.0
    if 'anomaly_score' in site_df.columns:
        site_df['_rank_score'] += site_df['anomaly_score'].fillna(0) * 0.4
    if 'avg_dqi_score' in site_df.columns:
        max_dqi = site_df['avg_dqi_score'].max()
        if max_dqi > 0:
            site_df['_rank_score'] += (site_df['avg_dqi_score'] / max_dqi) * 0.4
    if 'high_risk_count' in site_df.columns:
        max_hr = site_df['high_risk_count'].max()
        if max_hr > 0:
            site_df['_rank_score'] += (site_df['high_risk_count'] / max_hr) * 0.2

    top_sites_df = site_df.nlargest(top_sites, '_rank_score')
    print(f"  Selected {len(top_sites_df)} sites for detailed analysis")

    # Run multi-agent analysis
    print("\n" + "=" * 70)
    print("STEP 4: RUN MULTI-AGENT ANALYSIS")
    print("=" * 70)

    recommendations = []
    all_analyses = {}

    for idx, (_, row) in enumerate(top_sites_df.iterrows()):
        site_data = row.to_dict()
        site_id = site_data.get('site_id', 'Unknown')
        study = site_data.get('study', 'Unknown')

        print(f"  [{idx+1}/{len(top_sites_df)}] Analyzing {site_id} ({study})...", end="")

        recommendation, analyses = mas.analyze_site(site_data)
        recommendations.append(recommendation)
        all_analyses[f"{study}_{site_id}"] = [asdict(a) for a in analyses]

        risk_symbol = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}.get(recommendation.risk_category, "⚪")
        print(f" {risk_symbol} {recommendation.risk_category}")

    # Sort by priority
    recommendations.sort(key=lambda x: (x.priority, -x.composite_score))

    # Save outputs
    print("\n" + "=" * 70)
    print("STEP 5: SAVE OUTPUTS")
    print("=" * 70)

    PHASE_07_DIR.mkdir(parents=True, exist_ok=True)

    # Save recommendations CSV
    recs_data = [asdict(r) for r in recommendations]
    recs_df = pd.DataFrame(recs_data)
    recs_df.to_csv(RECOMMENDATIONS_PATH, index=False, encoding='utf-8')
    print(f"  [OK] Saved: {RECOMMENDATIONS_PATH}")

    # Save detailed analysis JSON
    analysis_output = {
        'generated': datetime.now().isoformat(),
        'sites_analyzed': len(recommendations),
        'portfolio_context': mas.portfolio_context,
        'site_analyses': {k: v for k, v in list(all_analyses.items())[:20]}
    }
    with open(AGENT_ANALYSIS_PATH, 'w', encoding='utf-8') as f:
        json.dump(analysis_output, f, indent=2, default=str)
    print(f"  [OK] Saved: {AGENT_ANALYSIS_PATH}")

    # Generate and save report
    report = generate_report(recommendations, all_analyses, mas.portfolio_context)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"  [OK] Saved: {REPORT_PATH}")

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    critical = sum(1 for r in recommendations if r.risk_category == "Critical")
    high = sum(1 for r in recommendations if r.risk_category == "High")
    medium = sum(1 for r in recommendations if r.risk_category == "Medium")
    low = sum(1 for r in recommendations if r.risk_category == "Low")
    escalations = sum(1 for r in recommendations if r.escalation_required)

    print(f"""
Sites Analyzed: {len(recommendations)}

Risk Distribution:
  🔴 Critical: {critical}
  🟠 High: {high}
  🟡 Medium: {medium}
  🟢 Low: {low}

Escalations Required: {escalations}

Top 5 Priority Sites:""")

    for rec in recommendations[:5]:
        print(f"  {rec.priority}. {rec.site_id} ({rec.study}) - {rec.risk_category} - Score: {rec.composite_score:.3f}")

    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print(f"""
1. Review: {REPORT_PATH}
2. Check critical sites requiring escalation
3. Run: python src/08_site_clustering.py
""")

    return True


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="JAVELIN.AI Multi-Agent Analysis System")
    parser.add_argument("--model", type=str, default="mistral", help="Ollama model to use")
    parser.add_argument("--top-sites", type=int, default=TOP_SITES_TO_ANALYZE, help="Number of top sites to analyze")
    parser.add_argument("--fast", action="store_true", help="Skip LLM, use rule-based analysis only")

    args = parser.parse_args()

    success = run_multi_agent_analysis(
        model=args.model,
        top_sites=args.top_sites,
        use_llm=not args.fast
    )

    if not success:
        exit(1)

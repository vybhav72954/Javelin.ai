"""
Javelin.AI - Step 7: Multi-Agent Recommendation System
=======================================================

WHAT THIS DOES:
---------------
Replaces single LLM recommendations with a team of specialized AI agents,
each analyzing sites from their domain expertise, then synthesizing
multi-perspective recommendations.

AGENT ARCHITECTURE:
-------------------
┌─────────────────────────────────────────────────────────────────┐
│                     COORDINATOR AGENT                           │
│         (Synthesizes all perspectives, prioritizes actions)     │
└─────────────────────────────────────────────────────────────────┘
                              ▲
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  SAFETY AGENT   │ │   DQ AGENT      │ │ PERFORMANCE     │
│                 │ │                 │ │    AGENT        │
│ • SAE pending   │ │ • Completeness  │ │ • Site trends   │
│ • Adverse events│ │ • Timeliness    │ │ • Benchmarking  │
│ • Patient safety│ │ • Coding status │ │ • Efficiency    │
│ • Regulatory    │ │ • Data integrity│ │ • Patterns      │
└─────────────────┘ └─────────────────┘ └─────────────────┘

WHY MULTI-AGENT:
----------------
1. Domain expertise: Each agent specializes in its area
2. Comprehensive analysis: Multiple perspectives on same data
3. Prioritized actions: Coordinator weighs and ranks recommendations
4. Transparency: Clear reasoning from each domain
5. Scalability: Easy to add new specialized agents

Usage:
    python src/07_multi_agent_system.py
    python src/07_multi_agent_system.py --model mistral
    python src/07_multi_agent_system.py --top-sites 20

Outputs:
    - outputs/multi_agent_recommendations.csv
    - outputs/multi_agent_report.md
    - outputs/agent_analysis.json
"""

import pandas as pd
import numpy as np
import json
import requests
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')


# ============================================================================
# CONFIGURATION
# ============================================================================

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"

# Input files
SITE_DQI_PATH = OUTPUT_DIR / "master_site_with_dqi.csv"
SUBJECT_DQI_PATH = OUTPUT_DIR / "master_subject_with_dqi.csv"
ANOMALIES_PATH = OUTPUT_DIR / "anomalies_detected.csv"
SITE_ANOMALY_SCORES_PATH = OUTPUT_DIR / "site_anomaly_scores.csv"

# Ollama Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "mistral"

# Agent Configuration
TOP_SITES_TO_ANALYZE = 50  # Number of high-risk sites for full agent analysis
AGENT_TIMEOUT = 30  # seconds per agent call (reduced from 60)
VERBOSE = True  # Show detailed progress


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class AgentAnalysis:
    """Result from a single agent's analysis."""
    agent_name: str
    agent_role: str
    risk_assessment: str  # CRITICAL, HIGH, MEDIUM, LOW
    key_findings: List[str]
    recommendations: List[str]
    confidence: float  # 0-1
    reasoning: str


@dataclass
class SiteRecommendation:
    """Final multi-agent recommendation for a site."""
    study: str
    site_id: str
    country: str
    region: str
    overall_priority: str  # CRITICAL, HIGH, MEDIUM, LOW
    overall_risk_score: float
    safety_analysis: Optional[AgentAnalysis]
    dq_analysis: Optional[AgentAnalysis]
    performance_analysis: Optional[AgentAnalysis]
    coordinator_synthesis: str
    top_actions: List[str]
    estimated_impact: str


# ============================================================================
# OLLAMA LLM INTEGRATION
# ============================================================================

class OllamaLLM:
    """Local LLM integration using Ollama."""

    def __init__(self, model: str = DEFAULT_MODEL):
        self.model = model
        self.available = False
        self._check_availability()

    def _check_availability(self):
        """Check if Ollama is running and model is available."""
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'].split(':')[0] for m in models]

                if self.model not in model_names and models:
                    self.model = model_names[0]
                    print(f"  [INFO] Using available model: {self.model}")

                # Quick test
                test_response = self._generate("Say OK", max_tokens=10)
                if test_response:
                    self.available = True
        except Exception as e:
            print(f"  [WARNING] Ollama not available: {str(e)[:50]}")

    def _generate(self, prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> Optional[str]:
        """Generate text using Ollama."""
        try:
            response = requests.post(
                OLLAMA_URL,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": temperature
                    }
                },
                timeout=AGENT_TIMEOUT
            )
            if response.status_code == 200:
                return response.json().get('response', '').strip()
        except Exception:
            pass
        return None

    def generate(self, prompt: str, max_tokens: int = 500) -> Optional[str]:
        """Public generate method."""
        if not self.available:
            return None
        return self._generate(prompt, max_tokens)


# ============================================================================
# AGENT BASE CLASS
# ============================================================================

class BaseAgent:
    """Base class for all specialized agents."""

    def __init__(self, llm: OllamaLLM):
        self.llm = llm
        self.name = "BaseAgent"
        self.role = "General Analysis"
        self.expertise = []

    def analyze(self, site_data: Dict, anomalies: List[Dict] = None) -> AgentAnalysis:
        """Analyze a site and return findings. Override in subclasses."""
        raise NotImplementedError

    def _build_prompt(self, site_data: Dict, context: str, question: str) -> str:
        """Build a prompt for the LLM."""
        return f"""You are a {self.role} expert analyzing clinical trial site data.

SITE CONTEXT:
{context}

YOUR TASK:
{question}

Provide a concise, actionable analysis in 2-3 sentences. Focus on specific issues and concrete recommendations.
Do not use bullet points. Be direct and specific."""

    def _parse_risk_level(self, text: str) -> str:
        """Parse risk level from LLM response."""
        text_upper = text.upper()
        if 'CRITICAL' in text_upper:
            return 'CRITICAL'
        elif 'HIGH' in text_upper:
            return 'HIGH'
        elif 'MEDIUM' in text_upper or 'MODERATE' in text_upper:
            return 'MEDIUM'
        else:
            return 'LOW'

    def _rule_based_analysis(self, site_data: Dict, anomalies: List[Dict] = None) -> AgentAnalysis:
        """Fallback rule-based analysis when LLM is unavailable."""
        raise NotImplementedError


# ============================================================================
# SAFETY AGENT
# ============================================================================

class SafetyAgent(BaseAgent):
    """Specializes in patient safety and regulatory compliance."""

    def __init__(self, llm: OllamaLLM):
        super().__init__(llm)
        self.name = "SafetyAgent"
        self.role = "Patient Safety & Pharmacovigilance"
        self.expertise = [
            "SAE (Serious Adverse Event) monitoring",
            "Adverse event coding (MedDRA)",
            "Regulatory compliance",
            "Patient safety signals"
        ]

    def analyze(self, site_data: Dict, anomalies: List[Dict] = None) -> AgentAnalysis:
        """Analyze site from safety perspective."""

        # Extract safety-relevant metrics
        sae_pending = site_data.get('sae_pending_count_sum', 0) or 0
        uncoded_meddra = site_data.get('uncoded_meddra_count_sum', 0) or 0
        subject_count = site_data.get('subject_count', 0) or 1
        high_risk_count = site_data.get('high_risk_count', 0) or 0
        site_risk = site_data.get('site_risk_category', 'Unknown')

        # Check for safety-related anomalies
        safety_anomalies = []
        if anomalies:
            safety_anomalies = [a for a in anomalies if
                               'SAE' in str(a.get('description', '')).upper() or
                               'MEDDRA' in str(a.get('description', '')).upper() or
                               a.get('detection_method') in ['SAE_NOT_FLAGGED', 'SAE_WITHOUT_CODING']]

        # Build context
        context = f"""
Site: {site_data.get('site_id')} ({site_data.get('country')})
Study: {site_data.get('study')}
Subjects: {subject_count}
Current Risk Category: {site_risk}

SAFETY METRICS:
- Pending SAE Reviews: {sae_pending}
- Uncoded MedDRA Terms: {uncoded_meddra}
- High-Risk Subjects: {high_risk_count} ({high_risk_count/subject_count*100:.1f}%)
- Safety Anomalies Detected: {len(safety_anomalies)}
"""

        if safety_anomalies:
            context += "\nSAFETY ANOMALIES:\n"
            for a in safety_anomalies[:3]:
                context += f"- {a.get('description', 'Unknown')}\n"

        # Try LLM analysis first
        if self.llm and self.llm.available:
            prompt = f"""Clinical trial safety analysis for {site_data.get('site_id')} ({site_data.get('country')}):
- Pending SAE: {sae_pending}
- Uncoded MedDRA: {uncoded_meddra}
- High-risk subjects: {high_risk_count}/{subject_count}
- Safety anomalies: {len(safety_anomalies)}

Assess safety risk in 2 sentences. End with: Risk Level: CRITICAL/HIGH/MEDIUM/LOW"""

            response = self.llm.generate(prompt, max_tokens=150)

            if response:
                return AgentAnalysis(
                    agent_name=self.name,
                    agent_role=self.role,
                    risk_assessment=self._parse_risk_level(response),
                    key_findings=self._extract_findings(site_data, sae_pending, uncoded_meddra, safety_anomalies),
                    recommendations=self._generate_recommendations(sae_pending, uncoded_meddra),
                    confidence=0.85,
                    reasoning=response
                )

        # Fallback to rule-based
        return self._rule_based_analysis(site_data, anomalies)

    def _extract_findings(self, site_data: Dict, sae_pending: int, uncoded_meddra: int,
                         anomalies: List[Dict]) -> List[str]:
        """Extract key safety findings."""
        findings = []

        if sae_pending > 0:
            findings.append(f"{sae_pending} SAE reviews pending regulatory submission")
        if uncoded_meddra > 0:
            findings.append(f"{uncoded_meddra} adverse event terms require MedDRA coding")
        if any(a.get('detection_method') == 'SAE_NOT_FLAGGED' for a in anomalies):
            findings.append("Site has pending SAE but not flagged as High risk - classification gap")
        if any(a.get('detection_method') == 'SAE_WITHOUT_CODING' for a in anomalies):
            findings.append("SAE present without corresponding coded terms - workflow issue")

        if not findings:
            findings.append("No immediate safety concerns identified")

        return findings

    def _generate_recommendations(self, sae_pending: int, uncoded_meddra: int) -> List[str]:
        """Generate safety recommendations."""
        recs = []

        if sae_pending > 5:
            recs.append("URGENT: Expedite SAE review - regulatory timeline at risk")
        elif sae_pending > 0:
            recs.append("Complete pending SAE reviews within 24-48 hours")

        if uncoded_meddra > 10:
            recs.append("Prioritize MedDRA coding backlog - safety signal detection compromised")
        elif uncoded_meddra > 0:
            recs.append("Route uncoded adverse events to medical coding team")

        if not recs:
            recs.append("Maintain current safety monitoring protocols")

        return recs

    def _rule_based_analysis(self, site_data: Dict, anomalies: List[Dict] = None) -> AgentAnalysis:
        """Rule-based safety analysis when LLM unavailable."""
        sae_pending = site_data.get('sae_pending_count_sum', 0) or 0
        uncoded_meddra = site_data.get('uncoded_meddra_count_sum', 0) or 0

        # Determine risk level
        if sae_pending > 10 or (anomalies and any(a.get('detection_method') == 'SAE_NOT_FLAGGED' for a in anomalies)):
            risk = 'CRITICAL'
        elif sae_pending > 5 or uncoded_meddra > 10:
            risk = 'HIGH'
        elif sae_pending > 0 or uncoded_meddra > 0:
            risk = 'MEDIUM'
        else:
            risk = 'LOW'

        safety_anomalies = [a for a in (anomalies or []) if 'SAE' in str(a.get('description', '')).upper()]

        reasoning = f"Safety assessment based on {sae_pending} pending SAE and {uncoded_meddra} uncoded terms. "
        if safety_anomalies:
            reasoning += f"Found {len(safety_anomalies)} safety-related anomalies. "
        reasoning += f"Overall safety risk: {risk}."

        return AgentAnalysis(
            agent_name=self.name,
            agent_role=self.role,
            risk_assessment=risk,
            key_findings=self._extract_findings(site_data, sae_pending, uncoded_meddra, safety_anomalies),
            recommendations=self._generate_recommendations(sae_pending, uncoded_meddra),
            confidence=0.70,
            reasoning=reasoning
        )


# ============================================================================
# DATA QUALITY AGENT
# ============================================================================

class DataQualityAgent(BaseAgent):
    """Specializes in data completeness, timeliness, and integrity."""

    def __init__(self, llm: OllamaLLM):
        super().__init__(llm)
        self.name = "DataQualityAgent"
        self.role = "Data Quality & Completeness"
        self.expertise = [
            "Data completeness assessment",
            "Timeliness monitoring",
            "Query management",
            "Data integrity checks"
        ]

    def analyze(self, site_data: Dict, anomalies: List[Dict] = None) -> AgentAnalysis:
        """Analyze site from data quality perspective."""

        # Extract DQ metrics
        missing_visits = site_data.get('missing_visit_count_sum', 0) or 0
        missing_pages = site_data.get('missing_pages_count_sum', 0) or 0
        max_days_outstanding = site_data.get('max_days_outstanding_sum', 0) or 0
        max_days_page_missing = site_data.get('max_days_page_missing_sum', 0) or 0
        lab_issues = site_data.get('lab_issues_count_sum', 0) or 0
        edrr_issues = site_data.get('edrr_open_issues_sum', 0) or 0
        subjects_with_issues = site_data.get('subjects_with_issues', 0) or 0
        subject_count = site_data.get('subject_count', 0) or 1
        avg_dqi = site_data.get('avg_dqi_score', 0) or 0

        # DQ-related anomalies
        dq_anomalies = []
        if anomalies:
            dq_anomalies = [a for a in anomalies if
                          a.get('detection_method') in ['STALE_MISSING_DATA', 'SINGLE_ISSUE_DOMINANCE',
                                                        'ZERO_ISSUES_HIGH_VOLUME'] or
                          'MISSING' in str(a.get('description', '')).upper() or
                          'LAB' in str(a.get('description', '')).upper()]

        context = f"""
Site: {site_data.get('site_id')} ({site_data.get('country')})
Study: {site_data.get('study')}
Subjects: {subject_count} | With Issues: {subjects_with_issues} ({subjects_with_issues/subject_count*100:.1f}%)
Average DQI Score: {avg_dqi:.3f}

DATA QUALITY METRICS:
- Missing Visits: {missing_visits}
- Missing Pages: {missing_pages}
- Max Days Outstanding: {max_days_outstanding}
- Max Days Page Missing: {max_days_page_missing}
- Lab Data Issues: {lab_issues}
- EDRR Open Issues: {edrr_issues}
- DQ Anomalies Detected: {len(dq_anomalies)}
"""

        if dq_anomalies:
            context += "\nDATA QUALITY ANOMALIES:\n"
            for a in dq_anomalies[:3]:
                context += f"- {a.get('description', 'Unknown')}\n"

        # Try LLM analysis
        if self.llm and self.llm.available:
            prompt = f"""Data quality analysis for {site_data.get('site_id')} ({site_data.get('country')}):
- Missing visits: {missing_visits}, Missing pages: {missing_pages}
- Max days outstanding: {max_days_outstanding}
- Lab issues: {lab_issues}, EDRR issues: {edrr_issues}
- DQI score: {avg_dqi:.3f}

Assess data quality risk in 2 sentences. End with: Risk Level: CRITICAL/HIGH/MEDIUM/LOW"""

            response = self.llm.generate(prompt, max_tokens=150)

            if response:
                return AgentAnalysis(
                    agent_name=self.name,
                    agent_role=self.role,
                    risk_assessment=self._parse_risk_level(response),
                    key_findings=self._extract_findings(site_data, dq_anomalies),
                    recommendations=self._generate_recommendations(site_data),
                    confidence=0.85,
                    reasoning=response
                )

        return self._rule_based_analysis(site_data, anomalies)

    def _extract_findings(self, site_data: Dict, anomalies: List[Dict]) -> List[str]:
        """Extract key DQ findings."""
        findings = []

        missing_visits = site_data.get('missing_visit_count_sum', 0) or 0
        missing_pages = site_data.get('missing_pages_count_sum', 0) or 0
        max_days = max(site_data.get('max_days_outstanding_sum', 0) or 0,
                      site_data.get('max_days_page_missing_sum', 0) or 0)

        if missing_visits > 5:
            findings.append(f"{missing_visits} visits not completed - protocol deviation risk")
        if missing_pages > 10:
            findings.append(f"{missing_pages} CRF pages missing - data completeness issue")
        if max_days > 60:
            findings.append(f"Data outstanding for {max_days}+ days - stale query issue")

        for a in anomalies:
            if a.get('detection_method') == 'SINGLE_ISSUE_DOMINANCE':
                findings.append("Single issue type dominates - systemic problem identified")
                break

        if not findings:
            findings.append("Data quality within acceptable parameters")

        return findings

    def _generate_recommendations(self, site_data: Dict) -> List[str]:
        """Generate DQ recommendations."""
        recs = []

        missing_visits = site_data.get('missing_visit_count_sum', 0) or 0
        missing_pages = site_data.get('missing_pages_count_sum', 0) or 0
        max_days = max(site_data.get('max_days_outstanding_sum', 0) or 0,
                      site_data.get('max_days_page_missing_sum', 0) or 0)

        if max_days > 60:
            recs.append("Escalate stale queries to site management - unresolved for 60+ days")
        if missing_visits > 5:
            recs.append("Schedule site call to address missed visits and document reasons")
        if missing_pages > 10:
            recs.append("Issue batch query for missing CRF pages")

        if not recs:
            recs.append("Continue routine data monitoring")

        return recs

    def _rule_based_analysis(self, site_data: Dict, anomalies: List[Dict] = None) -> AgentAnalysis:
        """Rule-based DQ analysis."""
        missing_visits = site_data.get('missing_visit_count_sum', 0) or 0
        missing_pages = site_data.get('missing_pages_count_sum', 0) or 0
        max_days = max(site_data.get('max_days_outstanding_sum', 0) or 0,
                      site_data.get('max_days_page_missing_sum', 0) or 0)
        avg_dqi = site_data.get('avg_dqi_score', 0) or 0

        # Determine risk
        if avg_dqi > 0.4 or max_days > 90:
            risk = 'CRITICAL'
        elif avg_dqi > 0.2 or max_days > 60 or missing_pages > 20:
            risk = 'HIGH'
        elif avg_dqi > 0.1 or missing_visits > 5 or missing_pages > 5:
            risk = 'MEDIUM'
        else:
            risk = 'LOW'

        dq_anomalies = [a for a in (anomalies or []) if
                       a.get('detection_method') in ['STALE_MISSING_DATA', 'SINGLE_ISSUE_DOMINANCE']]

        reasoning = f"DQ assessment: DQI={avg_dqi:.3f}, {missing_visits} missing visits, {missing_pages} missing pages, {max_days} days max outstanding. "
        reasoning += f"Overall DQ risk: {risk}."

        return AgentAnalysis(
            agent_name=self.name,
            agent_role=self.role,
            risk_assessment=risk,
            key_findings=self._extract_findings(site_data, dq_anomalies),
            recommendations=self._generate_recommendations(site_data),
            confidence=0.70,
            reasoning=reasoning
        )


# ============================================================================
# PERFORMANCE AGENT
# ============================================================================

class PerformanceAgent(BaseAgent):
    """Specializes in site performance trends and benchmarking."""

    def __init__(self, llm: OllamaLLM):
        super().__init__(llm)
        self.name = "PerformanceAgent"
        self.role = "Site Performance & Operations"
        self.expertise = [
            "Site performance trends",
            "Cross-study benchmarking",
            "Operational efficiency",
            "Resource allocation"
        ]
        self.portfolio_stats = {}  # Will be populated with portfolio benchmarks

    def set_portfolio_stats(self, stats: Dict):
        """Set portfolio-level statistics for benchmarking."""
        self.portfolio_stats = stats

    def analyze(self, site_data: Dict, anomalies: List[Dict] = None) -> AgentAnalysis:
        """Analyze site from performance perspective."""

        subject_count = site_data.get('subject_count', 0) or 1
        high_risk_count = site_data.get('high_risk_count', 0) or 0
        high_risk_pct = high_risk_count / subject_count * 100
        avg_dqi = site_data.get('avg_dqi_score', 0) or 0

        # Cross-study anomalies
        cross_study_anomalies = []
        if anomalies:
            cross_study_anomalies = [a for a in anomalies if
                                     a.get('anomaly_type') == 'CROSS_STUDY_ANOMALY' or
                                     a.get('detection_method') in ['REPEAT_OFFENDER', 'MAJORITY_HIGH_RISK',
                                                                   'HIGH_ISSUE_DENSITY', 'STUDY_CONCENTRATION']]

        # Benchmarking
        portfolio_avg_dqi = self.portfolio_stats.get('avg_dqi', 0.045)
        portfolio_avg_high_risk_pct = self.portfolio_stats.get('avg_high_risk_pct', 10)

        context = f"""
Site: {site_data.get('site_id')} ({site_data.get('country')})
Study: {site_data.get('study')}
Region: {site_data.get('region')}

PERFORMANCE METRICS:
- Subjects: {subject_count}
- High-Risk Subjects: {high_risk_count} ({high_risk_pct:.1f}%)
- Average DQI: {avg_dqi:.3f}

PORTFOLIO BENCHMARKS:
- Portfolio Average DQI: {portfolio_avg_dqi:.3f}
- Site vs Portfolio: {'+' if avg_dqi > portfolio_avg_dqi else ''}{((avg_dqi/portfolio_avg_dqi)-1)*100:.0f}% 
- Portfolio Avg High-Risk Rate: {portfolio_avg_high_risk_pct:.1f}%
- Site vs Portfolio: {'+' if high_risk_pct > portfolio_avg_high_risk_pct else ''}{high_risk_pct - portfolio_avg_high_risk_pct:.1f}pp

CROSS-STUDY PATTERNS: {len(cross_study_anomalies)} anomalies
"""

        if cross_study_anomalies:
            for a in cross_study_anomalies[:2]:
                context += f"- {a.get('description', 'Unknown')}\n"

        # Try LLM analysis
        if self.llm and self.llm.available:
            portfolio_avg_dqi = self.portfolio_stats.get('avg_dqi', 0.045)
            prompt = f"""Site performance analysis for {site_data.get('site_id')} ({site_data.get('country')}):
- DQI: {avg_dqi:.3f} (portfolio avg: {portfolio_avg_dqi:.3f}, ratio: {avg_dqi/portfolio_avg_dqi:.1f}x)
- High-risk subjects: {high_risk_pct:.1f}%
- Cross-study anomalies: {len(cross_study_anomalies)}

Assess operational performance risk in 2 sentences. End with: Risk Level: CRITICAL/HIGH/MEDIUM/LOW"""

            response = self.llm.generate(prompt, max_tokens=150)

            if response:
                return AgentAnalysis(
                    agent_name=self.name,
                    agent_role=self.role,
                    risk_assessment=self._parse_risk_level(response),
                    key_findings=self._extract_findings(site_data, cross_study_anomalies, portfolio_avg_dqi),
                    recommendations=self._generate_recommendations(site_data, cross_study_anomalies),
                    confidence=0.85,
                    reasoning=response
                )

        return self._rule_based_analysis(site_data, anomalies)

    def _extract_findings(self, site_data: Dict, anomalies: List[Dict], portfolio_avg: float) -> List[str]:
        """Extract performance findings."""
        findings = []

        avg_dqi = site_data.get('avg_dqi_score', 0) or 0
        high_risk_pct = (site_data.get('high_risk_count', 0) or 0) / (site_data.get('subject_count', 1) or 1) * 100

        if avg_dqi > portfolio_avg * 2:
            findings.append(f"Site DQI ({avg_dqi:.3f}) is {avg_dqi/portfolio_avg:.1f}x portfolio average - significant underperformance")
        elif avg_dqi > portfolio_avg:
            findings.append(f"Site DQI above portfolio average ({avg_dqi:.3f} vs {portfolio_avg:.3f})")

        if high_risk_pct > 25:
            findings.append(f"{high_risk_pct:.0f}% high-risk subjects - well above typical rate")

        for a in anomalies:
            if a.get('detection_method') == 'REPEAT_OFFENDER':
                findings.append("Site identified as repeat offender across multiple studies")
                break

        if not findings:
            findings.append("Site performing within expected parameters")

        return findings

    def _generate_recommendations(self, site_data: Dict, anomalies: List[Dict]) -> List[str]:
        """Generate performance recommendations."""
        recs = []

        avg_dqi = site_data.get('avg_dqi_score', 0) or 0

        is_repeat_offender = any(a.get('detection_method') == 'REPEAT_OFFENDER' for a in anomalies)

        if is_repeat_offender:
            recs.append("Cross-functional review required - site shows pattern across multiple programs")

        if avg_dqi > 0.3:
            recs.append("Consider site capability assessment and targeted training")
        elif avg_dqi > 0.15:
            recs.append("Schedule site quality meeting with CRA")

        if not recs:
            recs.append("Continue routine monitoring")

        return recs

    def _rule_based_analysis(self, site_data: Dict, anomalies: List[Dict] = None) -> AgentAnalysis:
        """Rule-based performance analysis."""
        avg_dqi = site_data.get('avg_dqi_score', 0) or 0
        portfolio_avg = self.portfolio_stats.get('avg_dqi', 0.045)

        is_repeat_offender = any(a.get('detection_method') == 'REPEAT_OFFENDER' for a in (anomalies or []))

        # Determine risk
        if is_repeat_offender or avg_dqi > portfolio_avg * 5:
            risk = 'CRITICAL'
        elif avg_dqi > portfolio_avg * 3:
            risk = 'HIGH'
        elif avg_dqi > portfolio_avg * 1.5:
            risk = 'MEDIUM'
        else:
            risk = 'LOW'

        reasoning = f"Performance vs portfolio: DQI {avg_dqi:.3f} vs avg {portfolio_avg:.3f} ({avg_dqi/portfolio_avg:.1f}x). "
        if is_repeat_offender:
            reasoning += "Site is repeat offender across studies. "
        reasoning += f"Performance risk: {risk}."

        return AgentAnalysis(
            agent_name=self.name,
            agent_role=self.role,
            risk_assessment=risk,
            key_findings=self._extract_findings(site_data, anomalies or [], portfolio_avg),
            recommendations=self._generate_recommendations(site_data, anomalies or []),
            confidence=0.70,
            reasoning=reasoning
        )


# ============================================================================
# COORDINATOR AGENT
# ============================================================================

class CoordinatorAgent(BaseAgent):
    """Synthesizes analyses from all agents and prioritizes actions."""

    def __init__(self, llm: OllamaLLM):
        super().__init__(llm)
        self.name = "CoordinatorAgent"
        self.role = "Multi-Agent Coordinator"

    def synthesize(self, site_data: Dict,
                   safety_analysis: AgentAnalysis,
                   dq_analysis: AgentAnalysis,
                   performance_analysis: AgentAnalysis) -> Tuple[str, str, List[str]]:
        """
        Synthesize all agent analyses into final recommendation.

        Returns:
            Tuple of (overall_priority, synthesis_text, top_actions)
        """

        # Determine overall priority (worst of all agents, with safety weighted higher)
        risk_levels = {
            'CRITICAL': 4,
            'HIGH': 3,
            'MEDIUM': 2,
            'LOW': 1
        }

        # Safety gets extra weight
        safety_score = risk_levels.get(safety_analysis.risk_assessment, 1) * 1.5
        dq_score = risk_levels.get(dq_analysis.risk_assessment, 1)
        perf_score = risk_levels.get(performance_analysis.risk_assessment, 1)

        max_score = max(safety_score, dq_score, perf_score)

        if max_score >= 5:  # CRITICAL safety or very high combined
            overall_priority = 'CRITICAL'
        elif max_score >= 3.5:
            overall_priority = 'HIGH'
        elif max_score >= 2:
            overall_priority = 'MEDIUM'
        else:
            overall_priority = 'LOW'

        # Collect all recommendations
        all_recs = []
        if safety_analysis.risk_assessment in ['CRITICAL', 'HIGH']:
            all_recs.extend([(r, 'safety', safety_score) for r in safety_analysis.recommendations])
        if dq_analysis.risk_assessment in ['CRITICAL', 'HIGH']:
            all_recs.extend([(r, 'dq', dq_score) for r in dq_analysis.recommendations])
        if performance_analysis.risk_assessment in ['CRITICAL', 'HIGH']:
            all_recs.extend([(r, 'perf', perf_score) for r in performance_analysis.recommendations])

        # If no high-priority recs, include medium ones
        if not all_recs:
            all_recs.extend([(r, 'safety', safety_score) for r in safety_analysis.recommendations])
            all_recs.extend([(r, 'dq', dq_score) for r in dq_analysis.recommendations])

        # Sort by score and dedupe
        all_recs.sort(key=lambda x: -x[2])
        seen = set()
        top_actions = []
        for rec, source, score in all_recs:
            if rec not in seen:
                seen.add(rec)
                top_actions.append(rec)
            if len(top_actions) >= 5:
                break

        # Build synthesis
        if self.llm and self.llm.available:
            prompt = f"""Synthesize for {site_data.get('site_id')}:
Safety: {safety_analysis.risk_assessment} - {safety_analysis.key_findings[0] if safety_analysis.key_findings else 'N/A'}
DQ: {dq_analysis.risk_assessment} - {dq_analysis.key_findings[0] if dq_analysis.key_findings else 'N/A'}
Performance: {performance_analysis.risk_assessment}

Write 2-sentence executive summary. Overall priority: {overall_priority}. State primary concern and top action."""

            synthesis = self.llm.generate(prompt, max_tokens=100)
            if synthesis:
                return overall_priority, synthesis, top_actions

        # Rule-based synthesis
        primary_concern = "safety" if safety_score >= dq_score and safety_score >= perf_score else \
                         "data quality" if dq_score >= perf_score else "performance"

        synthesis = f"Site requires {overall_priority} priority attention. "
        synthesis += f"Primary concern is {primary_concern} (Safety: {safety_analysis.risk_assessment}, "
        synthesis += f"DQ: {dq_analysis.risk_assessment}, Performance: {performance_analysis.risk_assessment}). "
        synthesis += f"Recommend immediate focus on {top_actions[0] if top_actions else 'comprehensive review'}."

        return overall_priority, synthesis, top_actions


# ============================================================================
# MULTI-AGENT SYSTEM
# ============================================================================

class MultiAgentSystem:
    """Orchestrates all agents for comprehensive site analysis."""

    def __init__(self, model: str = DEFAULT_MODEL):
        print(f"\n[1/4] Initializing Multi-Agent System...")

        # Initialize LLM
        self.llm = OllamaLLM(model=model)

        if self.llm.available:
            print(f"  ✅ LLM Ready: {self.llm.model}")
        else:
            print(f"  ⚠️  LLM not available - using rule-based analysis")
            print(f"     To enable AI: Install Ollama, run 'ollama pull mistral', then 'ollama serve'")

        # Initialize agents
        self.safety_agent = SafetyAgent(self.llm)
        self.dq_agent = DataQualityAgent(self.llm)
        self.performance_agent = PerformanceAgent(self.llm)
        self.coordinator = CoordinatorAgent(self.llm)

        print(f"  ✅ Agents initialized: Safety, DataQuality, Performance, Coordinator")

    def set_portfolio_context(self, site_df: pd.DataFrame):
        """Set portfolio-level statistics for benchmarking."""
        stats = {
            'avg_dqi': site_df['avg_dqi_score'].mean(),
            'std_dqi': site_df['avg_dqi_score'].std(),
            'avg_high_risk_pct': (site_df['high_risk_count'].sum() / site_df['subject_count'].sum()) * 100,
            'total_sites': len(site_df),
            'total_subjects': site_df['subject_count'].sum()
        }
        self.performance_agent.set_portfolio_stats(stats)
        print(f"  ✅ Portfolio context set: {stats['total_sites']} sites, {stats['total_subjects']:,} subjects")

    def analyze_site(self, site_data: Dict, site_anomalies: List[Dict] = None,
                     verbose: bool = False) -> SiteRecommendation:
        """Run full multi-agent analysis on a single site."""
        import time

        site_id = site_data.get('site_id', 'Unknown')

        # Run each agent with timing
        if verbose:
            print(f"    → Safety Agent analyzing {site_id}...", end=" ", flush=True)
        start = time.time()
        safety_analysis = self.safety_agent.analyze(site_data, site_anomalies)
        if verbose:
            print(f"({time.time()-start:.1f}s) [{safety_analysis.risk_assessment}]")

        if verbose:
            print(f"    → DQ Agent analyzing {site_id}...", end=" ", flush=True)
        start = time.time()
        dq_analysis = self.dq_agent.analyze(site_data, site_anomalies)
        if verbose:
            print(f"({time.time()-start:.1f}s) [{dq_analysis.risk_assessment}]")

        if verbose:
            print(f"    → Performance Agent analyzing {site_id}...", end=" ", flush=True)
        start = time.time()
        performance_analysis = self.performance_agent.analyze(site_data, site_anomalies)
        if verbose:
            print(f"({time.time()-start:.1f}s) [{performance_analysis.risk_assessment}]")

        if verbose:
            print(f"    → Coordinator synthesizing...", end=" ", flush=True)
        start = time.time()
        # Coordinate and synthesize
        overall_priority, synthesis, top_actions = self.coordinator.synthesize(
            site_data, safety_analysis, dq_analysis, performance_analysis
        )
        if verbose:
            print(f"({time.time()-start:.1f}s) → {overall_priority}")

        # Calculate overall risk score
        risk_scores = {'CRITICAL': 1.0, 'HIGH': 0.75, 'MEDIUM': 0.5, 'LOW': 0.25}
        avg_risk = (
            risk_scores.get(safety_analysis.risk_assessment, 0.5) * 0.4 +
            risk_scores.get(dq_analysis.risk_assessment, 0.5) * 0.35 +
            risk_scores.get(performance_analysis.risk_assessment, 0.5) * 0.25
        )

        # Estimate impact
        if overall_priority == 'CRITICAL':
            impact = "High - Immediate regulatory or patient safety impact"
        elif overall_priority == 'HIGH':
            impact = "Significant - Timeline or data quality at risk"
        elif overall_priority == 'MEDIUM':
            impact = "Moderate - Requires attention within 2 weeks"
        else:
            impact = "Low - Routine monitoring sufficient"

        return SiteRecommendation(
            study=site_data.get('study', 'Unknown'),
            site_id=site_data.get('site_id', 'Unknown'),
            country=site_data.get('country', 'Unknown'),
            region=site_data.get('region', 'Unknown'),
            overall_priority=overall_priority,
            overall_risk_score=round(avg_risk, 3),
            safety_analysis=safety_analysis,
            dq_analysis=dq_analysis,
            performance_analysis=performance_analysis,
            coordinator_synthesis=synthesis,
            top_actions=top_actions,
            estimated_impact=impact
        )


# ============================================================================
# REPORT GENERATION
# ============================================================================

def generate_multi_agent_report(recommendations: List[SiteRecommendation],
                                llm_available: bool) -> str:
    """Generate markdown report from multi-agent analysis."""

    critical_count = sum(1 for r in recommendations if r.overall_priority == 'CRITICAL')
    high_count = sum(1 for r in recommendations if r.overall_priority == 'HIGH')

    report = f"""# JAVELIN.AI - Multi-Agent Recommendation Report

*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
*Analysis Mode: {'AI-Enhanced (LLM)' if llm_available else 'Rule-Based'}*

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Sites Analyzed | {len(recommendations)} |
| Critical Priority | {critical_count} |
| High Priority | {high_count} |
| AI-Enhanced Analysis | {'Yes' if llm_available else 'No (Rule-Based)'} |

---

## Agent Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     COORDINATOR AGENT                           │
│         (Synthesizes all perspectives, prioritizes actions)     │
└─────────────────────────────────────────────────────────────────┘
                              ▲
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│  SAFETY AGENT   │ │   DQ AGENT      │ │ PERFORMANCE     │
│  (40% weight)   │ │  (35% weight)   │ │   (25% weight)  │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

---

## Critical Priority Sites

"""

    critical_sites = [r for r in recommendations if r.overall_priority == 'CRITICAL']

    if critical_sites:
        for i, rec in enumerate(critical_sites[:10], 1):
            report += f"""
### {i}. {rec.study} - {rec.site_id} ({rec.country})

**Overall Risk Score:** {rec.overall_risk_score:.2f}

| Agent | Risk Level | Key Finding |
|-------|------------|-------------|
| Safety | {rec.safety_analysis.risk_assessment} | {rec.safety_analysis.key_findings[0] if rec.safety_analysis.key_findings else 'N/A'} |
| Data Quality | {rec.dq_analysis.risk_assessment} | {rec.dq_analysis.key_findings[0] if rec.dq_analysis.key_findings else 'N/A'} |
| Performance | {rec.performance_analysis.risk_assessment} | {rec.performance_analysis.key_findings[0] if rec.performance_analysis.key_findings else 'N/A'} |

**Coordinator Synthesis:**
{rec.coordinator_synthesis}

**Recommended Actions:**
"""
            for action in rec.top_actions[:3]:
                report += f"- {action}\n"
            report += f"\n**Estimated Impact:** {rec.estimated_impact}\n"
    else:
        report += "*No critical priority sites identified.*\n"

    report += """

---

## High Priority Sites

"""

    high_sites = [r for r in recommendations if r.overall_priority == 'HIGH'][:10]

    if high_sites:
        report += "| Study | Site | Country | Risk Score | Safety | DQ | Performance | Top Action |\n"
        report += "|-------|------|---------|------------|--------|----|-----------|-----------|\n"

        for rec in high_sites:
            top_action = rec.top_actions[0][:40] + '...' if rec.top_actions and len(rec.top_actions[0]) > 40 else (rec.top_actions[0] if rec.top_actions else 'N/A')
            report += f"| {rec.study[:15]} | {rec.site_id} | {rec.country} | {rec.overall_risk_score:.2f} | {rec.safety_analysis.risk_assessment} | {rec.dq_analysis.risk_assessment} | {rec.performance_analysis.risk_assessment} | {top_action} |\n"
    else:
        report += "*No high priority sites identified.*\n"

    report += """

---

## Action Summary by Domain

### Safety Actions
"""

    safety_actions = set()
    for rec in recommendations:
        if rec.safety_analysis.risk_assessment in ['CRITICAL', 'HIGH']:
            safety_actions.update(rec.safety_analysis.recommendations)

    for action in list(safety_actions)[:5]:
        report += f"- {action}\n"

    report += """

### Data Quality Actions
"""

    dq_actions = set()
    for rec in recommendations:
        if rec.dq_analysis.risk_assessment in ['CRITICAL', 'HIGH']:
            dq_actions.update(rec.dq_analysis.recommendations)

    for action in list(dq_actions)[:5]:
        report += f"- {action}\n"

    report += """

### Performance Actions
"""

    perf_actions = set()
    for rec in recommendations:
        if rec.performance_analysis.risk_assessment in ['CRITICAL', 'HIGH']:
            perf_actions.update(rec.performance_analysis.recommendations)

    for action in list(perf_actions)[:5]:
        report += f"- {action}\n"

    report += """

---

*Report generated by JAVELIN.AI Multi-Agent System*
"""

    return report


# ============================================================================
# MAIN FUNCTION
# ============================================================================

def run_multi_agent_system(model: str = DEFAULT_MODEL, top_sites: int = TOP_SITES_TO_ANALYZE,
                           use_llm: bool = True):
    """Main function to run multi-agent analysis.

    Args:
        model: LLM model to use (default: mistral)
        top_sites: Number of sites to analyze
        use_llm: If False, use rule-based only (faster)
    """

    print("=" * 70)
    print("JAVELIN.AI - MULTI-AGENT RECOMMENDATION SYSTEM")
    print("=" * 70)
    print(f"\nProject Root: {PROJECT_ROOT}")

    # =========================================================================
    # Initialize System
    # =========================================================================
    mas = MultiAgentSystem(model=model)

    # Override LLM if --fast mode
    if not use_llm:
        mas.llm.available = False
        print(f"  [INFO] Fast mode enabled - using rule-based analysis only")

    # =========================================================================
    # Load Data
    # =========================================================================
    print(f"\n[2/4] Loading data...")

    if not SITE_DQI_PATH.exists():
        print(f"  ❌ ERROR: {SITE_DQI_PATH} not found")
        return False

    site_df = pd.read_csv(SITE_DQI_PATH)
    print(f"  ✅ Loaded {len(site_df):,} sites")

    # Load anomalies
    anomalies_df = None
    if ANOMALIES_PATH.exists():
        anomalies_df = pd.read_csv(ANOMALIES_PATH)
        print(f"  ✅ Loaded {len(anomalies_df):,} anomalies")

    # Set portfolio context
    mas.set_portfolio_context(site_df)

    # =========================================================================
    # Select Sites for Analysis
    # =========================================================================
    print(f"\n[3/4] Selecting top {top_sites} sites for analysis...")

    # Prioritize by: 1) anomaly score, 2) DQI score, 3) high risk count
    if SITE_ANOMALY_SCORES_PATH.exists():
        anomaly_scores = pd.read_csv(SITE_ANOMALY_SCORES_PATH)
        # Merge anomaly scores
        site_df = site_df.merge(
            anomaly_scores[['study', 'site_id', 'anomaly_score', 'anomaly_count']],
            on=['study', 'site_id'],
            how='left'
        )
        site_df['anomaly_score'] = site_df['anomaly_score'].fillna(0)
        site_df['anomaly_count'] = site_df['anomaly_count'].fillna(0)
    else:
        site_df['anomaly_score'] = 0
        site_df['anomaly_count'] = 0

    # Sort by composite score
    site_df['composite_score'] = (
        site_df['anomaly_score'] * 0.4 +
        site_df['avg_dqi_score'] / site_df['avg_dqi_score'].max() * 0.4 +
        site_df['high_risk_count'] / site_df['high_risk_count'].max() * 0.2
    )

    top_site_df = site_df.nlargest(top_sites, 'composite_score')
    print(f"  ✅ Selected {len(top_site_df)} sites for full agent analysis")

    # =========================================================================
    # Run Multi-Agent Analysis
    # =========================================================================
    print(f"\n[4/4] Running multi-agent analysis...")
    print(f"  Note: Each site requires 4 agent calls. With LLM, this takes ~10-30s per site.")

    recommendations = []
    total_start = datetime.now()

    for idx, (_, site_row) in enumerate(top_site_df.iterrows(), 1):
        site_data = site_row.to_dict()

        # Get anomalies for this site
        site_anomalies = []
        if anomalies_df is not None:
            site_anomalies = anomalies_df[
                (anomalies_df['study'] == site_data['study']) &
                (anomalies_df['site_id'] == site_data['site_id'])
            ].to_dict('records')

        # Progress header
        print(f"\n  [{idx}/{len(top_site_df)}] {site_data.get('study')} - {site_data.get('site_id')} ({site_data.get('country')})")

        # Run analysis with verbose output
        rec = mas.analyze_site(site_data, site_anomalies, verbose=True)
        recommendations.append(rec)

    elapsed = (datetime.now() - total_start).total_seconds()
    print(f"\n  ✅ Completed analysis for {len(recommendations)} sites in {elapsed:.1f}s")

    # =========================================================================
    # Save Outputs
    # =========================================================================
    print("\n" + "=" * 70)
    print("SAVING OUTPUTS")
    print("=" * 70)

    OUTPUT_DIR.mkdir(exist_ok=True)

    # 1. CSV output
    csv_data = []
    for rec in recommendations:
        csv_data.append({
            'study': rec.study,
            'site_id': rec.site_id,
            'country': rec.country,
            'region': rec.region,
            'overall_priority': rec.overall_priority,
            'overall_risk_score': rec.overall_risk_score,
            'safety_risk': rec.safety_analysis.risk_assessment,
            'dq_risk': rec.dq_analysis.risk_assessment,
            'performance_risk': rec.performance_analysis.risk_assessment,
            'top_action': rec.top_actions[0] if rec.top_actions else '',
            'coordinator_synthesis': rec.coordinator_synthesis[:500],
            'estimated_impact': rec.estimated_impact
        })

    csv_path = OUTPUT_DIR / "multi_agent_recommendations.csv"
    pd.DataFrame(csv_data).to_csv(csv_path, index=False)
    print(f"\n✅ Saved: {csv_path}")

    # 2. JSON output (detailed)
    json_data = {
        'generated_at': datetime.now().isoformat(),
        'model': mas.llm.model if mas.llm.available else 'rule-based',
        'llm_available': mas.llm.available,
        'sites_analyzed': len(recommendations),
        'priority_summary': {
            'critical': sum(1 for r in recommendations if r.overall_priority == 'CRITICAL'),
            'high': sum(1 for r in recommendations if r.overall_priority == 'HIGH'),
            'medium': sum(1 for r in recommendations if r.overall_priority == 'MEDIUM'),
            'low': sum(1 for r in recommendations if r.overall_priority == 'LOW')
        },
        'recommendations': [
            {
                'study': r.study,
                'site_id': r.site_id,
                'country': r.country,
                'overall_priority': r.overall_priority,
                'risk_score': r.overall_risk_score,
                'safety': asdict(r.safety_analysis),
                'dq': asdict(r.dq_analysis),
                'performance': asdict(r.performance_analysis),
                'synthesis': r.coordinator_synthesis,
                'actions': r.top_actions,
                'impact': r.estimated_impact
            }
            for r in recommendations[:20]  # Top 20 for JSON
        ]
    }

    json_path = OUTPUT_DIR / "agent_analysis.json"
    with open(json_path, 'w') as f:
        json.dump(json_data, f, indent=2, default=str)
    print(f"✅ Saved: {json_path}")

    # 3. Markdown report
    report = generate_multi_agent_report(recommendations, mas.llm.available)
    report_path = OUTPUT_DIR / "multi_agent_report.md"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"✅ Saved: {report_path}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    critical_count = sum(1 for r in recommendations if r.overall_priority == 'CRITICAL')
    high_count = sum(1 for r in recommendations if r.overall_priority == 'HIGH')

    print(f"""
MULTI-AGENT ANALYSIS COMPLETE
=============================

Configuration:
  Model: {mas.llm.model if mas.llm.available else 'Rule-Based'}
  AI-Enhanced: {'Yes' if mas.llm.available else 'No'}
  Sites Analyzed: {len(recommendations)}

Priority Distribution:
  CRITICAL: {critical_count}
  HIGH: {high_count}
  MEDIUM: {sum(1 for r in recommendations if r.overall_priority == 'MEDIUM')}
  LOW: {sum(1 for r in recommendations if r.overall_priority == 'LOW')}

Agent Breakdown:
  Safety Agent: Analyzed SAE, adverse events, patient safety
  DQ Agent: Analyzed completeness, timeliness, data integrity
  Performance Agent: Benchmarked against portfolio, identified patterns
  Coordinator: Synthesized multi-perspective recommendations
""")

    if critical_count > 0:
        print("TOP CRITICAL SITES:")
        for r in [r for r in recommendations if r.overall_priority == 'CRITICAL'][:5]:
            print(f"  • {r.study} - {r.site_id} ({r.country}): {r.top_actions[0] if r.top_actions else 'Review required'}")

    print("\n" + "=" * 70)
    print("OUTPUTS")
    print("=" * 70)
    print(f"""
1. {csv_path}
2. {json_path}
3. {report_path}
""")

    return True


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import sys

    model = DEFAULT_MODEL
    top_sites = TOP_SITES_TO_ANALYZE
    use_llm = True

    # Parse arguments
    if "--model" in sys.argv:
        idx = sys.argv.index("--model")
        if idx + 1 < len(sys.argv):
            model = sys.argv[idx + 1]

    if "--top-sites" in sys.argv:
        idx = sys.argv.index("--top-sites")
        if idx + 1 < len(sys.argv):
            top_sites = int(sys.argv[idx + 1])

    if "--fast" in sys.argv:
        use_llm = False
        print("[INFO] Fast mode: Using rule-based analysis (no LLM)")

    if "--help" in sys.argv or "-h" in sys.argv:
        print("""
JAVELIN.AI Multi-Agent System

Usage:
    python 07_multi_agent_system.py [options]

Options:
    --model MODEL      LLM model to use (default: mistral)
    --top-sites N      Number of sites to analyze (default: 50)
    --fast             Use rule-based analysis only (no LLM, faster)
    --help, -h         Show this help message

Examples:
    python 07_multi_agent_system.py --top-sites 10
    python 07_multi_agent_system.py --fast --top-sites 100
    python 07_multi_agent_system.py --model llama3 --top-sites 20
""")
        sys.exit(0)

    success = run_multi_agent_system(model=model, top_sites=top_sites, use_llm=use_llm)
    if not success:
        exit(1)

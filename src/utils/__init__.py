"""
JAVELIN.AI - Shared Utilities
=============================

This module contains reusable functions extracted from phase scripts
to eliminate code duplication and ensure consistency.

Modules:
    - data_loader: Excel reading, column finding, standardization
    - validation: Data quality checks, outlier capping, safe aggregations
    - dqi_calculator: DQI scoring, risk categorization, aggregations

Usage:
------
from utils import find_column, standardize_columns, read_excel_smart
from utils import validate_loaded_data, cap_outliers, safe_max
from utils import calculate_component_score, assign_risk_categories
"""

# Data Loading Utilities
from .data_loader import (
    find_column,
    standardize_columns,
    read_excel_smart,
    detect_header_row,
)

# Validation Utilities
from .validation import (
    validate_loaded_data,
    cap_outliers,
    safe_max,
    safe_mean,
    fill_missing_categoricals,
    validate_required_columns,
)

# DQI Calculation Utilities
from .dqi_calculator import (
    calculate_component_score,
    calculate_dqi_with_weights,
    assign_risk_categories,
    calculate_reference_max,
    calculate_subject_dqi,
    get_risk_distribution,
    validate_dqi_weights,
)

# Aggregation Utilities
from .aggregation import (
    aggregate_to_site,
    aggregate_to_study,
    aggregate_to_region,
    aggregate_to_country,
    assign_aggregated_risk,
    calculate_risk_rates,
)

from .encoding_fix import force_utf8

__all__ = [
    # Data Loader
    'find_column',
    'standardize_columns',
    'read_excel_smart',
    'detect_header_row',
    # Validation
    'validate_loaded_data',
    'cap_outliers',
    'safe_max',
    'safe_mean',
    'fill_missing_categoricals',
    'validate_required_columns',
    # DQI Calculator
    'calculate_component_score',
    'calculate_dqi_with_weights',
    'assign_risk_categories',
    'calculate_reference_max',
    'calculate_subject_dqi',
    'get_risk_distribution',
    'validate_dqi_weights',
    # Aggregation
    'aggregate_to_site',
    'aggregate_to_study',
    'aggregate_to_region',
    'aggregate_to_country',
    'assign_aggregated_risk',
    'calculate_risk_rates',
    # Encoding
    'force_utf8'
]

__version__ = '1.0.0'
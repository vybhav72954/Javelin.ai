"""
Debug Script - Inspect Excel File Structure
This will show you exactly what's in the first 15 rows of a failing file
"""

import pandas as pd
import sys

# One of the files that's failing according to your diagnostic report
TEST_FILE = r"Z:\PGDBA Content\Competition\Nest 2.0\data\Study 13_CPID_Input Files - Anonymization\Study 13_Visit Projection Tracker_14NOV2025_updated.xlsx"

print("=" * 70)
print("DEBUGGING FILE STRUCTURE")
print("=" * 70)
print(f"File: {TEST_FILE}")
print()

# Read first 15 rows with NO header assumption
df_raw = pd.read_excel(TEST_FILE, sheet_name=0, header=None, nrows=15)

print("First 15 rows (RAW - no header):")
print("-" * 70)
for i in range(len(df_raw)):
    row_str = ' | '.join(str(x) for x in df_raw.iloc[i].values[:8])  # First 8 columns
    print(f"Row {i}: {row_str}")

print()
print("=" * 70)
print("HEADER PATTERN DETECTION")
print("=" * 70)

# The patterns from your fixed code
header_patterns = [
    'Subject ID', 'Subject', 'Patient ID',
    'Site ID', 'Site Number', 'Site',
    'Visit', 'Days Outstanding',
    'Issue', 'Missing',
    'Review Status', 'Action Status',
    'Coding Status',
    'Open', 'Total',
    'Country', 'Region'
]

# Test each row
for i in range(min(15, len(df_raw))):
    row_str = ' '.join(df_raw.iloc[i].astype(str).tolist())
    pattern_matches = sum(1 for pattern in header_patterns if pattern in row_str)

    matched_patterns = [p for p in header_patterns if p in row_str]

    print(f"Row {i}: {pattern_matches} patterns matched")
    if matched_patterns:
        print(f"       Matched: {matched_patterns}")

print()
print("=" * 70)
print("TRYING TO LOAD WITH FIXED LOGIC")
print("=" * 70)

# Try the fixed logic
df = pd.read_excel(TEST_FILE, sheet_name=0, header=None)

header_row = 0
for i in range(min(10, len(df))):
    row_str = ' '.join(df.iloc[i].astype(str).tolist())
    pattern_matches = sum(1 for pattern in header_patterns if pattern in row_str)
    if pattern_matches >= 2:
        header_row = i
        print(f"✓ Found header at row {i} (with {pattern_matches} patterns)")
        break

# Re-read with detected header
df = pd.read_excel(TEST_FILE, sheet_name=0, header=header_row)

print(f"\nColumns found: {list(df.columns[:10])}")
print(f"Rows before cleaning: {len(df)}")

# Clean up
if len(df) > 0:
    first_col = df.columns[0]
    if first_col in df.columns:
        header_like = df[first_col].astype(str).str.contains(
            'Subject ID|Subject|Patient ID|Site|Responsible|Project Name',
            case=False,
            na=False
        )
        df = df[~header_like]
    df = df[df[first_col].notna()]

print(f"Rows after cleaning: {len(df)}")
print(f"\nFirst few rows of data:")
print(df.head(3))

if len(df) == 0:
    print("\n⚠️  STILL EMPTY after loading!")
else:
    print(f"\n✓ SUCCESS - Loaded {len(df)} rows")

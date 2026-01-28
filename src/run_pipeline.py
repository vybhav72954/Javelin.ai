#!/usr/bin/env python3
"""
JAVELIN.AI - Pipeline Orchestrator
===================================

End-to-end pipeline execution with dependency management, logging, and validation.

USAGE:
------
# Run all mandatory phases (01-09, excluding 00 and 04)
python src/run_pipeline.py --all

# Run specific phase only
python src/run_pipeline.py --phase 03

# Include diagnostics before running all phases
python src/run_pipeline.py --all --diagnostics

# Include knowledge graph (Phase 04)
python src/run_pipeline.py --all --include-kg

# Skip phases that have already completed
python src/run_pipeline.py --all --skip-completed

FEATURES:
---------
- Sequential execution with dependency checking
- Stop immediately on error (GCP compliance)
- Automatic directory creation
- Comprehensive logging to outputs/logs/ folder
- Progress tracking with tqdm
- Pre-flight validation checks
- Summary report at completion
- Skip completed phases (optional)

GCP COMPLIANCE:
---------------
- Full audit trail in log file
- Timestamps for all operations
- Error capture with context
- Traceability of all inputs/outputs
- Validation before execution

Author: JAVELIN.AI Team
Version: 1.2.0
Last Updated: 2026-01-28
"""

import sys
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
import time
import json
import os
import platform

try:
    from tqdm import tqdm

    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("WARNING: tqdm not installed. Progress bars disabled.")
    print("Install with: pip install tqdm")

try:
    import psutil

    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("WARNING: psutil not installed. Disk space check disabled.")
    print("Install with: pip install psutil")

try:
    sys.path.insert(0, str(Path(__file__).parent))
    from config import (
        PROJECT_ROOT, DATA_DIR, OUTPUT_DIR, SRC_DIR, LOGS_DIR,
        PHASE_DIRS, PHASE_METADATA, PIPELINE_DEFAULTS,
        ensure_output_dirs, get_phase_script_path, get_phase_defaults
    )
except ImportError:
    print("ERROR: Could not import config.py")
    print("Make sure config.py exists in src/ directory")
    sys.exit(1)


# ============================================================================
# LOGGING SETUP
# ============================================================================

class PipelineLogger:
    """Handles logging to both file and console with GCP compliance."""

    def __init__(self, log_file: Path):
        self.log_file = log_file
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.start_time = datetime.now()

        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("JAVELIN.AI - DATA QUALITY INTELLIGENCE PIPELINE\n")
            f.write("=" * 80 + "\n")
            f.write(f"Run ID: {self.log_file.stem}\n")
            f.write(f"Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"User: {platform.node()}\n")
            f.write(f"Python: {platform.python_version()}\n")
            f.write(f"Platform: {platform.system()} {platform.release()}\n")
            f.write(f"Project Root: {PROJECT_ROOT}\n")
            f.write("=" * 80 + "\n\n")

    def log(self, message: str, level: str = "INFO", console: bool = True):
        """Log message to file and optionally console."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_line = f"[{timestamp}] [{level}] {message}"

        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_line + "\n")

        if console:
            if level=="ERROR":
                print(f"ERROR: {message}")
            elif level=="WARNING":
                print(f"WARNING: {message}")
            elif level=="SUCCESS":
                print(f"SUCCESS: {message}")
            else:
                print(message)

    def section(self, title: str):
        """Log a section header."""
        separator = "=" * 80
        self.log("\n" + separator, console=False)
        self.log(title, console=True)
        self.log(separator, console=False)

    def phase_start(self, phase_num: str, phase_name: str):
        """Log phase start."""
        self.section(f"Phase {phase_num}: {phase_name}")
        self.log(f"Status: RUNNING", console=False)

    def phase_success(self, phase_num: str, duration: float, outputs: list):
        """Log phase success."""
        self.log(f"Status: SUCCESS", level="SUCCESS")
        self.log(f"Duration: {duration:.1f}s", console=False)
        if outputs:
            self.log(f"Outputs:", console=False)
            for output in outputs:
                self.log(f"  - {output}", console=False)

    def phase_error(self, phase_num: str, error_msg: str):
        """Log phase error."""
        self.log(f"Status: FAILED", level="ERROR")
        self.log(f"Error: {error_msg}", level="ERROR")

    def finalize(self, success: bool, phases_run: int, total_duration: float):
        """Write final summary."""
        self.section("PIPELINE SUMMARY")
        end_time = datetime.now()

        self.log(f"Completed: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        self.log(f"Total Duration: {total_duration:.1f}s ({total_duration / 60:.1f}m)")
        self.log(f"Phases Executed: {phases_run}")

        if success:
            self.log("Pipeline Status: COMPLETED SUCCESSFULLY", level="SUCCESS")
        else:
            self.log("Pipeline Status: FAILED", level="ERROR")

        self.log("=" * 80)
        self.log(f"\nLog saved to: {self.log_file}", console=True)


# ============================================================================
# PRE-FLIGHT CHECKS
# ============================================================================

def check_python_version(logger: PipelineLogger) -> bool:
    """Check Python version is >= 3.8."""
    version = sys.version_info
    required = (3, 8)

    if version >= required:
        logger.log(f"Python version: {version.major}.{version.minor}.{version.micro} (OK)",
                   console=False)
        return True
    else:
        logger.log(f"Python version: {version.major}.{version.minor}.{version.micro} "
                   f"(requires >= {required[0]}.{required[1]})", level="ERROR")
        return False


def check_required_packages(logger: PipelineLogger) -> bool:
    """Check required Python packages are installed."""
    required_packages = {
        'pandas':'pandas',
        'numpy':'numpy',
        'openpyxl':'openpyxl',
        'networkx':'networkx',
        'scikit-learn':'sklearn',
        'matplotlib':'matplotlib',
        'seaborn':'seaborn',
    }

    missing = []
    for display_name, import_name in required_packages.items():
        try:
            __import__(import_name)
            logger.log(f"Package {display_name}: OK", console=False)
        except ImportError:
            missing.append(display_name)
            logger.log(f"Package {display_name}: MISSING", level="WARNING", console=False)

    if missing:
        logger.log(f"Missing packages: {', '.join(missing)}", level="ERROR")
        logger.log("Install with: pip install " + " ".join(missing), level="ERROR")
        return False

    return True


def check_data_folder(logger: PipelineLogger) -> bool:
    """Check data folder exists and contains files."""
    if not DATA_DIR.exists():
        logger.log(f"Data folder not found: {DATA_DIR}", level="ERROR")
        return False

    excel_files = list(DATA_DIR.rglob("*.xlsx")) + list(DATA_DIR.rglob("*.xls"))

    if not excel_files:
        logger.log(f"No Excel files found in: {DATA_DIR}", level="ERROR")
        return False

    study_folders = [d for d in DATA_DIR.iterdir() if d.is_dir()]

    logger.log(f"Data folder: {DATA_DIR}", console=False)
    logger.log(f"Study folders: {len(study_folders)}", console=False)
    logger.log(f"Excel files: {len(excel_files)}", console=False)

    return True


def check_disk_space(logger: PipelineLogger, required_mb: int = 100) -> bool:
    """Check available disk space."""
    if not HAS_PSUTIL:
        logger.log("Disk space check skipped (psutil not installed)",
                   level="WARNING", console=False)
        return True

    try:
        usage = psutil.disk_usage(str(OUTPUT_DIR.parent))
        free_mb = usage.free / (1024 * 1024)

        if free_mb < required_mb:
            logger.log(f"Insufficient disk space: {free_mb:.1f} MB free "
                       f"(requires >= {required_mb} MB)", level="ERROR")
            return False

        logger.log(f"Disk space: {free_mb:.1f} MB free (OK)", console=False)
        return True
    except Exception as e:
        logger.log(f"Disk space check failed: {e}", level="WARNING", console=False)
        return True


def check_phase_dependencies(phase_num: str, logger: PipelineLogger) -> tuple:
    """Check if required output files from dependent phases exist."""
    metadata = PHASE_METADATA[phase_num]
    required_phases = metadata['requires']
    missing_outputs = []

    for req_phase in required_phases:
        req_metadata = PHASE_METADATA[req_phase]
        req_outputs = req_metadata['outputs']

        phase_output_exists = False
        for output_key in req_outputs:
            from config import OUTPUT_FILES
            if output_key in OUTPUT_FILES:
                output_file = OUTPUT_FILES[output_key]
                if output_file.exists():
                    phase_output_exists = True
                    break

        if not phase_output_exists:
            missing_outputs.append(f"Phase {req_phase} ({req_metadata['name']})")

    if missing_outputs:
        logger.log(f"Phase {phase_num} depends on: {', '.join(missing_outputs)}",
                   level="ERROR")
        return False, missing_outputs

    return True, []


def check_phase_completed(phase_num: str, logger: PipelineLogger) -> bool:
    """Check if a phase has already completed by checking for output files."""
    metadata = PHASE_METADATA[phase_num]
    required_outputs = metadata['outputs']

    if not required_outputs:
        return False

    from config import OUTPUT_FILES

    CORE_OUTPUTS = {
        '04':['knowledge_graph', 'knowledge_graph_nodes', 'knowledge_graph_summary'],
        '05':['executive_summary', 'recommendations_report', 'recommendations_by_site'],
        '08':['site_clusters', 'cluster_profiles', 'cluster_summary'],
    }

    if phase_num in CORE_OUTPUTS:
        core_outputs = CORE_OUTPUTS[phase_num]
        for output_key in core_outputs:
            if output_key in OUTPUT_FILES:
                output_file = OUTPUT_FILES[output_key]
                if not output_file.exists():
                    return False
        return True

    else:
        all_exist = True
        for output_key in required_outputs:
            if output_key in OUTPUT_FILES:
                output_file = OUTPUT_FILES[output_key]
                if not output_file.exists():
                    all_exist = False
                    break
        return all_exist

def run_preflight_checks(logger: PipelineLogger) -> bool:
    """Run all pre-flight checks."""
    logger.section("PRE-FLIGHT CHECKS")

    checks = [
        ("Python version", check_python_version),
        ("Required packages", check_required_packages),
        ("Data folder", check_data_folder),
        ("Disk space", check_disk_space),
    ]

    all_passed = True
    for check_name, check_func in checks:
        logger.log(f"Checking {check_name}...", console=False)
        try:
            passed = check_func(logger)
            if passed:
                logger.log(f"  [{check_name}] OK", console=True)
            else:
                logger.log(f"  [{check_name}] FAILED", level="ERROR", console=True)
                all_passed = False
        except Exception as e:
            logger.log(f"  [{check_name}] ERROR: {e}", level="ERROR", console=True)
            all_passed = False

    return all_passed


# ============================================================================
# PHASE EXECUTION
# ============================================================================

def build_phase_command(phase_num: str) -> list:
    """Build command to execute a phase script with default arguments."""
    script_path = get_phase_script_path(phase_num)
    cmd = [sys.executable, str(script_path)]

    defaults = get_phase_defaults(phase_num)
    if defaults:
        for key, value in defaults.items():
            arg_name = f"--{key.replace('_', '-')}"

            if value is None:
                continue

            if isinstance(value, bool):
                if value:
                    cmd.append(arg_name)
            else:
                cmd.extend([arg_name, str(value)])

    return cmd


def execute_phase(phase_num: str, logger: PipelineLogger, skip_completed: bool = False) -> bool:
    """Execute a single phase script."""
    metadata = PHASE_METADATA[phase_num]
    phase_name = metadata['name']

    logger.phase_start(phase_num, phase_name)

    # Check if phase already completed (if flag enabled)
    if skip_completed and check_phase_completed(phase_num, logger):
        logger.log(f"Phase {phase_num} outputs already exist - SKIPPING", level="INFO")
        print(f"\nPhase {phase_num}: {phase_name} - SKIPPED (outputs exist)")
        return True

    print(f"\nRunning Phase {phase_num}: {phase_name}...")

    deps_ok, missing = check_phase_dependencies(phase_num, logger)
    if not deps_ok:
        logger.phase_error(phase_num, f"Missing dependencies: {', '.join(missing)}")
        return False

    cmd = build_phase_command(phase_num)
    logger.log(f"Command: {' '.join(cmd)}", console=False)

    start_time = time.time()
    try:
        # Force UTF-8 encoding via environment variable
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'

        result = subprocess.run(
            cmd,
            capture_output=True,
            check=True,
            cwd=PROJECT_ROOT,
            env=env
        )

        duration = time.time() - start_time

        # Manually decode output with UTF-8
        stdout_text = result.stdout.decode('utf-8', errors='replace') if result.stdout else ''
        stderr_text = result.stderr.decode('utf-8', errors='replace') if result.stderr else ''

        if stdout_text:
            logger.log("STDOUT:", console=False)
            logger.log(stdout_text, console=False)
        if stderr_text:
            logger.log("STDERR:", console=False)
            logger.log(stderr_text, console=False)

        outputs = []
        for output_key in metadata['outputs']:
            from config import OUTPUT_FILES
            if output_key in OUTPUT_FILES:
                output_file = OUTPUT_FILES[output_key]
                if output_file.exists():
                    outputs.append(str(output_file.relative_to(PROJECT_ROOT)))

        logger.phase_success(phase_num, duration, outputs)
        print(f"  Phase {phase_num} completed in {duration:.1f}s")

        return True

    except subprocess.CalledProcessError as e:
        duration = time.time() - start_time
        error_msg = f"Exit code {e.returncode}"

        # Manually decode error output with UTF-8
        stdout_text = e.stdout.decode('utf-8', errors='replace') if e.stdout else ''
        stderr_text = e.stderr.decode('utf-8', errors='replace') if e.stderr else ''

        if stdout_text:
            logger.log("STDOUT:", console=False)
            logger.log(stdout_text, console=False)
        if stderr_text:
            logger.log("STDERR:", console=False)
            logger.log(stderr_text, console=False)
            error_msg += f" | {stderr_text[:200]}"

        logger.phase_error(phase_num, error_msg)
        print(f"  Phase {phase_num} FAILED after {duration:.1f}s")

        return False

    except Exception as e:
        duration = time.time() - start_time
        logger.phase_error(phase_num, str(e))
        print(f"  Phase {phase_num} FAILED after {duration:.1f}s: {e}")
        return False


def execute_pipeline(phases: list, logger: PipelineLogger, skip_completed: bool = False) -> tuple:
    """Execute multiple phases in sequence."""
    logger.section("PIPELINE EXECUTION")

    phases_run = 0

    if HAS_TQDM:
        phase_iterator = tqdm(phases, desc="Pipeline Progress", unit="phase")
    else:
        phase_iterator = phases

    for phase_num in phase_iterator:
        metadata = PHASE_METADATA[phase_num]

        if HAS_TQDM:
            phase_iterator.set_description(f"Phase {phase_num}: {metadata['name']}")

        success = execute_phase(phase_num, logger, skip_completed=skip_completed)
        phases_run += 1

        if not success:
            logger.log(f"\nPipeline stopped due to Phase {phase_num} failure",
                       level="ERROR", console=True)
            logger.log("Troubleshooting:", console=True)
            logger.log(f"  1. Check log file for detailed error messages", console=True)
            logger.log(f"  2. Verify Phase {phase_num} dependencies are met", console=True)
            logger.log(f"  3. Run phase manually: python {get_phase_script_path(phase_num)}",
                       console=True)
            logger.log(f"\nTo resume from Phase {phase_num}:", console=True)
            logger.log(f"  python src/run_pipeline.py --phase {phase_num}", console=True)
            return False, phases_run

    return True, phases_run


# ============================================================================
# MAIN PIPELINE ORCHESTRATION
# ============================================================================

def get_phases_to_run(args: argparse.Namespace) -> list:
    """Determine which phases to run based on CLI arguments."""
    if args.phase:
        phase_num = args.phase.zfill(2)
        if phase_num not in PHASE_METADATA:
            print(f"ERROR: Unknown phase: {args.phase}")
            print(f"Valid phases: {', '.join(sorted(PHASE_METADATA.keys()))}")
            sys.exit(1)
        return [phase_num]

    elif args.all:
        phases = []

        if args.diagnostics:
            phases.append('00')

        phases.extend(['01', '02', '03'])

        if args.include_kg:
            phases.append('04')

        phases.extend(['05', '06', '07', '08', '09'])

        return phases

    else:
        print("ERROR: Must specify either --all or --phase")
        print("Usage:")
        print("  python src/run_pipeline.py --all")
        print("  python src/run_pipeline.py --phase 03")
        sys.exit(1)


def main():
    """Main pipeline orchestrator."""
    parser = argparse.ArgumentParser(
        description="JAVELIN.AI - Data Quality Intelligence Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python src/run_pipeline.py --all
  python src/run_pipeline.py --all --diagnostics
  python src/run_pipeline.py --all --include-kg
  python src/run_pipeline.py --all --skip-completed
  python src/run_pipeline.py --phase 03

Logs are saved to: outputs/logs/pipeline_run_YYYYMMDD_HHMMSS.log
        """
    )

    parser.add_argument('--all', action='store_true',
                        help='Run all mandatory phases (01-09, excluding 00 and 04)')
    parser.add_argument('--phase', type=str,
                        help='Run specific phase only (e.g., 03)')
    parser.add_argument('--diagnostics', action='store_true',
                        help='Include Phase 00 (diagnostics) before running pipeline')
    parser.add_argument('--include-kg', action='store_true',
                        help='Include Phase 04 (knowledge graph generation)')
    parser.add_argument('--skip-completed', action='store_true',
                        help='Skip phases that have already generated outputs')

    args = parser.parse_args()

    if not args.all and not args.phase:
        parser.print_help()
        sys.exit(1)

    if args.phase and (args.diagnostics or args.include_kg):
        print("ERROR: --diagnostics and --include-kg only work with --all")
        sys.exit(1)

    ensure_output_dirs()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"pipeline_run_{timestamp}.log"
    logger = PipelineLogger(log_file)

    print("=" * 80)
    print("JAVELIN.AI - DATA QUALITY INTELLIGENCE PIPELINE")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Log file: {log_file}")
    if args.skip_completed:
        print("Mode: Skip completed phases")
    print("=" * 80)

    if not run_preflight_checks(logger):
        logger.log("\nPre-flight checks failed. Aborting pipeline.",
                   level="ERROR", console=True)
        logger.finalize(False, 0, 0)
        sys.exit(1)

    print("\nAll pre-flight checks passed!")

    phases = get_phases_to_run(args)

    logger.section("EXECUTION PLAN")
    logger.log(f"Phases to execute: {len(phases)}")
    for phase_num in phases:
        metadata = PHASE_METADATA[phase_num]
        optional_mark = " (optional)" if metadata['optional'] else ""
        logger.log(f"  Phase {phase_num}: {metadata['name']}{optional_mark}",
                   console=True)

    print(f"\nReady to execute {len(phases)} phase(s).")

    start_time = time.time()
    success, phases_run = execute_pipeline(phases, logger, skip_completed=args.skip_completed)
    total_duration = time.time() - start_time

    logger.finalize(success, phases_run, total_duration)

    print("\n" + "=" * 80)
    print("PIPELINE SUMMARY")
    print("=" * 80)
    print(f"Total Duration: {total_duration:.1f}s ({total_duration / 60:.1f}m)")
    print(f"Phases Executed: {phases_run}")

    if success:
        print("Status: COMPLETED SUCCESSFULLY")
        print("=" * 80)
        print(f"\nAll outputs saved to: {OUTPUT_DIR}")
        print(f"Log file: {log_file}")
        sys.exit(0)
    else:
        print("Status: FAILED")
        print("=" * 80)
        print(f"\nCheck log file for details: {log_file}")
        sys.exit(1)


if __name__=="__main__":
    main()

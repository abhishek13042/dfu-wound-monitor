"""
Phase 00 Verification Script — DFU-WoundMonitor.

This script checks the structural integrity, requirement traceability,
and spec completeness for Phase 00 (Project Definition & Setup).

It verifies:
1. All Phase 00 specification documents exist.
2. The Master Tracker (specs/MASTER_TRACKER.md) is updated.
3. The Traceability Matrix (specs/TRACEABILITY.md) maps all Phase 00 requirements.
4. The Open Questions tracking document (specs/phase-00/OPEN_QUESTIONS.md) exists.
"""

import sys
from pathlib import Path


def check_file_exists(file_path: Path) -> bool:
    """
    Check if a required file exists on the filesystem.

    Inputs:
        file_path: Path object pointing to the target file.

    Outputs:
        True if file exists, False otherwise.
    """
    return file_path.is_file()


def verify_phase_00_specifications(project_root: Path) -> list[str]:
    """
    Verify that all 7 required Phase 00 specification markdown files are present.

    Inputs:
        project_root: Path object pointing to the root directory of the repository.

    Outputs:
        List of missing specification file names. Returns empty list if all exist.
    """
    expected_spec_files = [
        "01-project-definition.md",
        "02-scope-and-mvp.md",
        "03-dataset-strategy.md",
        "04-system-requirements.md",
        "05-system-architecture.md",
        "06-evaluation-and-success-criteria.md",
        "07-risks-limitations-and-acceptance.md",
        "OPEN_QUESTIONS.md",
    ]

    phase_00_directory = project_root / "specs" / "phase-00"
    missing_files = []

    for file_name in expected_spec_files:
        target_path = phase_00_directory / file_name
        if not check_file_exists(target_path):
            missing_files.append(file_name)

    return missing_files


def verify_master_tracker(project_root: Path) -> bool:
    """
    Verify that specs/MASTER_TRACKER.md contains Phase 00 specification mappings.

    Inputs:
        project_root: Path object to the repository root.

    Outputs:
        True if the master tracker contains P00-S01 through P00-S07, False otherwise.
    """
    tracker_path = project_root / "specs" / "MASTER_TRACKER.md"
    if not check_file_exists(tracker_path):
        return False

    with open(tracker_path, encoding="utf-8") as tracker_file:
        content = tracker_file.read()

    # Check for expected specification IDs in tracker table
    expected_spec_ids = [
        "P00-S01",
        "P00-S02",
        "P00-S03",
        "P00-S04",
        "P00-S05",
        "P00-S06",
        "P00-S07",
    ]

    for spec_id in expected_spec_ids:
        if spec_id not in content:
            return False

    return True


def verify_traceability_matrix(project_root: Path) -> list[str]:
    """
    Verify that specs/TRACEABILITY.md contains entries for Phase 00 requirements.

    Inputs:
        project_root: Path object to the repository root.

    Outputs:
        List of requirement IDs missing from the traceability matrix.
    """
    traceability_path = project_root / "specs" / "TRACEABILITY.md"
    if not check_file_exists(traceability_path):
        return ["TRACEABILITY.md missing"]

    with open(traceability_path, encoding="utf-8") as matrix_file:
        matrix_content = matrix_file.read()

    # Sample check of key Phase 00 requirement IDs
    key_requirement_ids = [
        "REQ-P00-S01-001",
        "REQ-P00-S02-001",
        "REQ-P00-S03-001",
        "REQ-P00-S04-001",
        "REQ-P00-S05-001",
        "REQ-P00-S06-001",
        "REQ-P00-S07-001",
    ]

    missing_requirements = []
    for req_id in key_requirement_ids:
        if req_id not in matrix_content:
            missing_requirements.append(req_id)

    return missing_requirements


def run_phase_00_verification() -> bool:
    """
    Main entry point for running Phase 00 repository verification.

    Outputs:
        True if all Phase 00 checks pass, False otherwise.
    """
    project_root = Path(__file__).resolve().parents[2]

    print("==================================================")
    print("      DFU-WoundMonitor — Phase 00 Verification    ")
    print("==================================================")

    # 1. Verify specification files
    missing_specs = verify_phase_00_specifications(project_root)
    if missing_specs:
        print(f"[FAIL] Missing Phase 00 specifications: {missing_specs}")
        return False
    else:
        print("[PASS] All 7 Phase 00 specifications and OPEN_QUESTIONS.md exist.")

    # 2. Verify Master Tracker
    if not verify_master_tracker(project_root):
        print("[FAIL] Master Tracker (specs/MASTER_TRACKER.md) is incomplete.")
        return False
    else:
        print("[PASS] Master Tracker correctly lists Phase 00 specifications.")

    # 3. Verify Traceability Matrix
    missing_reqs = verify_traceability_matrix(project_root)
    if missing_reqs:
        print(f"[FAIL] Traceability Matrix missing requirements: {missing_reqs}")
        return False
    else:
        print("[PASS] Traceability Matrix maps Phase 00 requirements.")

    print("\n==================================================")
    print("            PHASE 00 VERIFICATION PASSED          ")
    print("==================================================")
    return True


if __name__ == "__main__":
    success = run_phase_00_verification()
    if not success:
        sys.exit(1)

"""
Unit test suite verifying Phase 00 specification and project setup integrity.
"""

from pathlib import Path
import unittest
from scripts.verify_phase_00 import (
    verify_phase_00_specifications,
    verify_master_tracker,
    verify_traceability_matrix,
)


def get_project_root() -> Path:
    """
    Utility function to return the repository root directory path.
    """
    return Path(__file__).parent.parent.parent


class TestPhase00Integrity(unittest.TestCase):
    """
    TestCase class for Phase 00 specification and governance verification.
    """

    def test_phase_00_specifications_exist(self) -> None:
        """
        Verify that all 7 Phase 00 markdown specs and OPEN_QUESTIONS.md are present.
        """
        project_root = get_project_root()
        missing_files = verify_phase_00_specifications(project_root)

        # Assert no files are missing
        self.assertEqual(len(missing_files), 0, f"Missing spec files: {missing_files}")

    def test_master_tracker_completeness(self) -> None:
        """
        Verify that specs/MASTER_TRACKER.md contains all P00 spec entries.
        """
        project_root = get_project_root()
        is_valid = verify_master_tracker(project_root)

        self.assertTrue(is_valid, "Master Tracker does not contain all P00 spec entries.")

    def test_traceability_matrix_completeness(self) -> None:
        """
        Verify that specs/TRACEABILITY.md contains Phase 00 requirement mappings.
        """
        project_root = get_project_root()
        missing_requirements = verify_traceability_matrix(project_root)

        self.assertEqual(len(missing_requirements), 0, f"Missing requirements: {missing_requirements}")


if __name__ == "__main__":
    unittest.main()

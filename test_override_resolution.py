"""
Service e2e tests for manual override resolution
(DAY_SCHEDULE / DAY_STATUS corrections in attendance_correction_log).

Runs entirely against an in-memory SQLite database — never touches the real
contragest.db. Modeled on the in-memory pattern from
test_pointage_reg_number.py / test_paired_attendance.py.

Run with:
    python -m pytest test_override_resolution.py -q --no-header
"""
import sys
import unittest
from datetime import date, datetime

sys.path.insert(0, ".")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from contragest.core.database import (
    Base,
    Employee,
    WorkSchedule,
    EmployeeSchedule,
    AttendanceCorrectionLog,
    AttendanceRecord,
)
from contragest.features.pointage.service import PointageService

TEST_DATE = "2026-07-31"


def _make_session():
    """Create a fresh in-memory SQLite session pre-loaded with schema."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


class TestOverrideResolution(unittest.TestCase):
    def setUp(self):
        self.session = _make_session()

        self.emp = Employee(
            first_name="Sam", last_name="Tester", registration_number="7007"
        )
        self.session.add(self.emp)
        self.session.flush()

        self.fixed = WorkSchedule(
            name="FixedShift", start_time="09:00", end_time="18:00"
        )
        self.test_shift = WorkSchedule(
            name="TestShift", start_time="08:00", end_time="17:00"
        )
        self.session.add_all([self.fixed, self.test_shift])
        self.session.flush()

        self.assignment = EmployeeSchedule(
            employee_id=self.emp.id,
            schedule_id=self.fixed.id,
            effective_date=date(2026, 1, 1),
        )
        self.session.add(self.assignment)
        self.session.commit()

        self.service = PointageService(self.session)
        self.reg = self.emp.registration_number

    def tearDown(self):
        self.session.close()

    def test_schedule_override_roundtrip(self):
        ok, msg = self.service.save_schedule_correction(
            self.reg, TEST_DATE, "TestShift"
        )
        self.assertTrue(ok, msg)

        self.assertEqual(
            self.service.get_schedule_override(self.reg, TEST_DATE), "TestShift"
        )
        sched = self.service.get_schedule_for_date(self.emp.id, TEST_DATE)
        self.assertIsNotNone(sched)
        self.assertEqual(sched.name, "TestShift")

        ok, msg = self.service.delete_schedule_correction(self.reg, TEST_DATE)
        self.assertTrue(ok, msg)
        self.assertIsNone(self.service.get_schedule_override(self.reg, TEST_DATE))

        reverted = self.service.get_schedule_for_date(self.emp.id, TEST_DATE)
        self.assertIsNotNone(reverted)
        self.assertEqual(reverted.name, "FixedShift")

    def test_status_override_roundtrip_via_enriched(self):
        punch = AttendanceRecord(
            employee_id=self.emp.id,
            zk_user_id=self.reg,
            punch_time=f"{TEST_DATE} 08:00:00",
            punch_type="check_in",
        )
        self.session.add(punch)
        self.session.commit()

        ok, msg = self.service.save_status_correction(self.reg, TEST_DATE, "AB")
        self.assertTrue(ok, msg)
        self.assertEqual(self.service.get_status_override(self.reg, TEST_DATE), "AB")

        enriched = self.service.get_attendance_records_enriched(
            employee_id=self.emp.id, start_date=TEST_DATE, end_date=TEST_DATE
        )
        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0]["status"], "AB")

        ok, msg = self.service.delete_status_correction(self.reg, TEST_DATE)
        self.assertTrue(ok, msg)
        self.assertIsNone(self.service.get_status_override(self.reg, TEST_DATE))

        enriched = self.service.get_attendance_records_enriched(
            employee_id=self.emp.id, start_date=TEST_DATE, end_date=TEST_DATE
        )
        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0]["status"], "P")

    def test_datetime_shift_date_is_normalized_and_deduped(self):
        ok, msg = self.service.save_schedule_correction(
            self.reg, datetime(2026, 7, 31, 9, 0), "TestShift"
        )
        self.assertTrue(ok, msg)
        self.assertEqual(
            self.service.get_schedule_override(self.reg, TEST_DATE), "TestShift"
        )

        ok, msg = self.service.save_schedule_correction(
            self.reg, "2026-07-31T09:00:00", "TestShift"
        )
        self.assertTrue(ok, msg)

        logs = (
            self.session.query(AttendanceCorrectionLog)
            .filter(AttendanceCorrectionLog.issue_type == "DAY_SCHEDULE")
            .all()
        )
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].shift_date, TEST_DATE)

    def test_empty_or_dash_status_code_is_rejected(self):
        ok, msg = self.service.save_status_correction(self.reg, TEST_DATE, "")
        self.assertFalse(ok)
        self.assertEqual(msg, "Invalid status code.")

        ok, msg = self.service.save_status_correction(self.reg, TEST_DATE, "-")
        self.assertFalse(ok)
        self.assertEqual(msg, "Invalid status code.")

        count = (
            self.session.query(AttendanceCorrectionLog)
            .filter(AttendanceCorrectionLog.issue_type == "DAY_STATUS")
            .count()
        )
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()

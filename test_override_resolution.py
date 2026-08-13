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

    # ── DAY_PROGRAM slot edits (set_punch_slot / move_punch_slot) ──────────

    def _seed_raw_punches(self, reg_date, in1=None, out1=None, in2=None, out2=None):
        """Insert raw AttendanceRecord rows (the enriched view pairs them)."""
        slots = [
            (in1, "check_in", 1), (out1, "check_out", 1),
            (in2, "check_in", 2), (out2, "check_out", 2),
        ]
        for time_str, ptype, _slot in slots:
            if not time_str:
                continue
            self.session.add(AttendanceRecord(
                employee_id=self.emp.id,
                zk_user_id=self.reg,
                punch_time=f"{reg_date} {time_str}:00",
                punch_type=ptype,
            ))
        self.session.commit()

    def test_set_punch_slot_writes_day_program_override(self):
        """set_punch_slot pins the slot via a DAY_PROGRAM override and the
        enriched view reads it back verbatim."""
        self._seed_raw_punches(TEST_DATE, in1="08:00", out1="17:00")

        ok, msg = self.service.set_punch_slot(
            self.reg, TEST_DATE, "IN 1", "09:30",
            admin_name="Tester", reason="Adjust",
        )
        self.assertTrue(ok, msg)

        prog = self.service._get_day_program(self.reg, TEST_DATE)
        self.assertEqual(prog["in1"], "09:30:00")
        self.assertEqual(prog["out1"], "17:00:00")

        records = self.service.get_attendance_records_enriched(
            reg_filter=self.reg, start_date=TEST_DATE, end_date=TEST_DATE)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["check_in"], "09:30:00")

    def test_set_punch_slot_clears_slot_with_dash(self):
        """time_val '-' clears the slot in the override."""
        self._seed_raw_punches(TEST_DATE, in1="08:00", out1="17:00")
        ok, msg = self.service.set_punch_slot(
            self.reg, TEST_DATE, "IN 1", "-", admin_name="Tester", reason="Remove")
        self.assertTrue(ok, msg)
        prog = self.service._get_day_program(self.reg, TEST_DATE)
        self.assertEqual(prog["in1"], "-")
        self.assertEqual(prog["out1"], "17:00:00")

    def test_move_punch_slot_same_day_moves_and_clears(self):
        """A same-day move updates BOTH slots in the single override (regression
        test for the two-independent-dicts bug that lost the destination)."""
        # Simulate a night-shift day: the slots are already pinned by an
        # override (raw-punch pairing for "18 -> 02" produces OUT 1 / IN 2).
        ok0, msg0 = self.service.save_day_program(
            self.reg, TEST_DATE,
            in1="-", out1="04:07:00", in2="17:44:00", out2="-",
            admin_name="Tester",
        )
        self.assertTrue(ok0, msg0)

        ok, msg = self.service.move_punch_slot(
            self.reg, TEST_DATE, "IN 2", TEST_DATE, "IN 1",
            admin_name="Tester", reason="Night shift",
        )
        self.assertTrue(ok, msg)

        prog = self.service._get_day_program(self.reg, TEST_DATE)
        self.assertEqual(prog["in1"], "17:44:00")
        self.assertEqual(prog["in2"], "-")
        self.assertEqual(prog["out1"], "04:07:00")

    def test_move_punch_slot_cross_date_writes_both_days(self):
        """A cross-date move writes overrides on both source and destination."""
        src = TEST_DATE
        dst = "2026-08-01"
        self._seed_raw_punches(src, in1="08:00", out1="17:00")
        self._seed_raw_punches(dst, in1="09:00", out1="18:00")

        ok, msg = self.service.move_punch_slot(
            self.reg, src, "IN 1", dst, "OUT 1",
            admin_name="Tester", reason="Cross-date",
        )
        self.assertTrue(ok, msg)

        src_prog = self.service._get_day_program(self.reg, src)
        self.assertEqual(src_prog["in1"], "-")

        dst_prog = self.service._get_day_program(self.reg, dst)
        self.assertEqual(dst_prog["out1"], "08:00:00")


if __name__ == "__main__":
    unittest.main()

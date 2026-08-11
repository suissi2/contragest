"""
Unit tests — verify that the Pointage service uses registration_number
(REG) as the ZK machine user ID, not the internal DB primary key.

Run with:
    python test_pointage_reg_number.py
"""
import sys
import unittest
from unittest.mock import MagicMock, patch, call
from datetime import date

sys.path.insert(0, ".")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from contragest.core.database import Base, Employee, AttendanceMachine, AttendanceRecord


def _make_session():
    """Create a fresh in-memory SQLite session pre-loaded with schema."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _seed(session):
    """Insert a machine and two employees (one with REG, one without)."""
    machine = AttendanceMachine(
        name="TestMachine", ip_address="10.0.0.1", port=4370, is_active=True
    )
    session.add(machine)

    emp_with_reg = Employee(
        first_name="Bilel", last_name="Ben Mansour", registration_number="1863"
    )
    emp_no_reg = Employee(
        first_name="Orphan", last_name="NoReg", registration_number=None
    )
    session.add_all([emp_with_reg, emp_no_reg])
    session.commit()
    return machine, emp_with_reg, emp_no_reg


class TestPushUsesRegNumber(unittest.TestCase):
    """push_employee_to_machine must use registration_number as ZK uid, not DB id."""

    def setUp(self):
        self.session = _make_session()
        self.machine, self.emp, self.emp_no_reg = _seed(self.session)

    def tearDown(self):
        self.session.close()

    def test_push_uses_registration_number_as_uid(self):
        from contragest.features.pointage.service import PointageService

        svc = PointageService(self.session)
        mock_connector = MagicMock()
        mock_connector.upload_user.return_value = True
        svc.connector = mock_connector

        result = svc.push_employee_to_machine(self.machine.id, self.emp.id)

        self.assertTrue(result)
        mock_connector.upload_user.assert_called_once()
        kwargs = mock_connector.upload_user.call_args
        # uid must be the REG number, not the DB id
        actual_uid = kwargs[1].get("uid") or kwargs[0][3]  # positional or keyword
        self.assertEqual(actual_uid, int(self.emp.registration_number),
                         f"Expected uid={self.emp.registration_number} but got uid={actual_uid}")
        self.assertNotEqual(actual_uid, self.emp.id,
                            "uid must NOT be the DB primary key")

    def test_push_skips_employee_with_no_reg(self):
        from contragest.features.pointage.service import PointageService

        svc = PointageService(self.session)
        mock_connector = MagicMock()
        svc.connector = mock_connector

        result = svc.push_employee_to_machine(self.machine.id, self.emp_no_reg.id)

        self.assertFalse(result, "Should return False for employee with no registration_number")
        mock_connector.upload_user.assert_not_called()

    def test_push_all_uses_registration_number(self):
        from contragest.features.pointage.service import PointageService

        svc = PointageService(self.session)
        mock_connector = MagicMock()
        mock_connector.upload_user.return_value = True
        svc.connector = mock_connector

        success, failed = svc.push_all_employees_to_machine(self.machine.id)

        # emp_with_reg → success; emp_no_reg → failed (no REG number)
        self.assertEqual(success, 1)
        self.assertEqual(failed, 1)

        # The only upload call must use the REG number
        mock_connector.upload_user.assert_called_once()
        kwargs = mock_connector.upload_user.call_args
        actual_uid = kwargs[1].get("uid") or kwargs[0][3]
        self.assertEqual(actual_uid, int(self.emp.registration_number))


class TestDownloadResolvesViaRegNumber(unittest.TestCase):
    """download_attendance must map ZK user_id (= REG) to the correct employee."""

    def setUp(self):
        self.session = _make_session()
        self.machine, self.emp, _ = _seed(self.session)

    def tearDown(self):
        self.session.close()

    def _fake_zk_record(self, user_id, timestamp="2026-03-04 07:14:00", punch=0):
        rec = MagicMock()
        rec.user_id = user_id
        rec.timestamp = timestamp
        rec.punch = punch
        return rec

    def test_known_reg_resolves_to_employee(self):
        from contragest.features.pointage.service import PointageService

        svc = PointageService(self.session)
        svc.connector = MagicMock()
        # ZK returns a record whose user_id == employee's registration_number
        svc.connector.get_attendance.return_value = [
            self._fake_zk_record(user_id=self.emp.registration_number)
        ]

        res = svc.download_attendance(self.machine.id)
        count = res[0] if isinstance(res, tuple) else res

        self.assertEqual(count, 1)
        stored = self.session.query(AttendanceRecord).first()
        self.assertIsNotNone(stored)
        self.assertEqual(stored.employee_id, self.emp.id,
                         "employee_id must resolve to DB id via registration_number")
        self.assertEqual(stored.zk_user_id, str(self.emp.registration_number))

    def test_unknown_reg_stores_null_employee(self):
        from contragest.features.pointage.service import PointageService

        svc = PointageService(self.session)
        svc.connector = MagicMock()
        svc.connector.get_attendance.return_value = [
            self._fake_zk_record(user_id="9999", timestamp="2026-03-04 08:00:00")
        ]

        res = svc.download_attendance(self.machine.id)
        count = res[0] if isinstance(res, tuple) else res

        self.assertEqual(count, 1)
        stored = self.session.query(AttendanceRecord).first()
        self.assertIsNone(stored.employee_id,
                          "employee_id should be None for unknown REG numbers")
        self.assertEqual(stored.zk_user_id, "9999",
                         "zk_user_id must always be stored for traceability")

    def test_duplicate_records_are_skipped(self):
        from contragest.features.pointage.service import PointageService

        svc = PointageService(self.session)
        svc.connector = MagicMock()
        rec = self._fake_zk_record(user_id="1863", timestamp="2026-03-04 07:14:00")
        svc.connector.get_attendance.return_value = [rec]

        res1 = svc.download_attendance(self.machine.id)
        count1 = res1[0] if isinstance(res1, tuple) else res1
        res2 = svc.download_attendance(self.machine.id)
        count2 = res2[0] if isinstance(res2, tuple) else res2

        self.assertEqual(count1, 1, "First download should store 1 record")
        self.assertEqual(count2, 0, "Second download of same record should be skipped (dedup)")
        self.assertEqual(self.session.query(AttendanceRecord).count(), 1)


class TestSyncStatusUsesRegNumber(unittest.TestCase):
    """get_employees_sync_status must compare by user_id (= REG), not uid slot."""

    def setUp(self):
        self.session = _make_session()
        self.machine, self.emp, _ = _seed(self.session)

    def tearDown(self):
        self.session.close()

    def test_on_machine_uses_user_id_field(self):
        from contragest.features.pointage.service import PointageService

        svc = PointageService(self.session)
        # Simulate a pyzk User with user_id = REG number (string)
        fake_user = MagicMock()
        fake_user.user_id = self.emp.registration_number  # "1863"
        fake_user.uid = 9999  # different from REG — old code would use this
        svc.connector = MagicMock()
        svc.connector.get_users.return_value = [fake_user]

        statuses = svc.get_employees_sync_status(self.machine.id)
        emp_status = next(s for s in statuses if s["id"] == self.emp.id)

        self.assertTrue(emp_status["on_machine"],
                        "Employee should be detected as on machine via user_id (REG), not uid slot")
        self.assertEqual(emp_status["registration_number"], self.emp.registration_number)


if __name__ == "__main__":
    print("=" * 60)
    print("Pointage REG NUMBER — Unit Tests")
    print("=" * 60)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.defaultTestLoader.loadTestsFromModule(
        sys.modules[__name__]
    ))
    sys.exit(0 if result.wasSuccessful() else 1)

import sys
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

sys.path.insert(0, ".")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contragest.core.database import Base, Employee, AttendanceRecord, AttendanceRecordBackup, Department, AttendanceMachine

def _make_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()

class TestPairedAttendance(unittest.TestCase):
    def setUp(self):
        self.session = _make_session()
        self.dept = Department(name="IT")
        self.session.add(self.dept)
        self.session.commit()

        self.emp1 = Employee(first_name="Alice", last_name="Smith", registration_number="100", department_id=self.dept.id, role_title="Dev")
        self.session.add(self.emp1)
        self.session.commit()

        self.machine = AttendanceMachine(name="M1", ip_address="1.1.1.1")
        self.session.add(self.machine)
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_pairing_logic(self):
        from contragest.features.pointage.service import PointageService
        svc = PointageService(self.session)
        
        # 1. Single punch (In only)
        rec1 = AttendanceRecord(employee_id=self.emp1.id, zk_user_id="100", punch_time="2026-03-01 08:00:00", punch_type="check_in", machine_id=self.machine.id)
        self.session.add(rec1)
        self.session.commit()
        
        enriched = svc.get_attendance_records_enriched(start_date="2026-03-01", end_date="2026-03-01")
        self.assertEqual(len(enriched), 1)
        self.assertEqual(enriched[0]["check_in"], "08:00:00")
        self.assertEqual(enriched[0]["check_out"], "-")
        
        # 2. Add second punch (Out)
        rec2 = AttendanceRecord(employee_id=self.emp1.id, zk_user_id="100", punch_time="2026-03-01 17:00:00", punch_type="check_out", machine_id=self.machine.id)
        self.session.add(rec2)
        self.session.commit()
        
        enriched = svc.get_attendance_records_enriched(start_date="2026-03-01", end_date="2026-03-01")
        self.assertEqual(len(enriched), 1) # Still one line per employee per day
        self.assertEqual(enriched[0]["check_in"], "08:00:00")
        self.assertEqual(enriched[0]["check_out"], "17:00:00")

    @patch("contragest.features.pointage.service.MachineConnector")
    def test_auto_backup_on_download(self, mock_connector_class):
        from contragest.features.pointage.service import PointageService
        
        # Setup mock connector
        mock_connector = mock_connector_class.return_value
        
        # 1. First sync: Check In only
        fake_rec1 = MagicMock()
        fake_rec1.user_id = "100"
        fake_rec1.timestamp = "2026-03-04 12:00:00"
        fake_rec1.punch = 0
        mock_connector.get_attendance.return_value = [fake_rec1]
        
        svc = PointageService(self.session)
        svc.connector = mock_connector
        
        svc.download_attendance(self.machine.id)
        
        backups = self.session.query(AttendanceRecordBackup).all()
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].check_in, "12:00:00")
        self.assertEqual(backups[0].check_out, "-")
        
        # 2. Second sync: Check Out added for same day/emp
        fake_rec2 = MagicMock()
        fake_rec2.user_id = "100"
        fake_rec2.timestamp = "2026-03-04 17:00:00"
        fake_rec2.punch = 1 # Check Out
        mock_connector.get_attendance.return_value = [fake_rec2]
        
        svc.download_attendance(self.machine.id)
        
        # Should still have 1 row in backup (UPSERT), but with check_out populated
        backups = self.session.query(AttendanceRecordBackup).all()
        self.assertEqual(len(backups), 1, "Should have upserted the existing paired backup")
        self.assertEqual(backups[0].check_in, "12:00:00")
        self.assertEqual(backups[0].check_out, "17:00:00")
        self.assertEqual(backups[0].employee_name, "Alice Smith")

    @patch("contragest.features.pointage.service.MachineConnector")
    def test_proximity_deduplication(self, mock_connector_class):
        from contragest.features.pointage.service import PointageService
        
        # Setup mock connector with two punches within 1 minute
        mock_connector = mock_connector_class.return_value
        
        fake_rec1 = MagicMock()
        fake_rec1.user_id = "100"
        fake_rec1.timestamp = "2026-03-05 08:00:00"
        fake_rec1.punch = 0
        
        fake_rec2 = MagicMock()
        fake_rec2.user_id = "100"
        fake_rec2.timestamp = "2026-03-05 08:00:45"  # 45 seconds later
        fake_rec2.punch = 0
        
        mock_connector.get_attendance.return_value = [fake_rec1, fake_rec2]
        
        svc = PointageService(self.session)
        svc.connector = mock_connector
        
        inserted, total = svc.download_attendance(self.machine.id)
        
        # Should only insert 1 record because the second is within the 5-minute debounce window
        self.assertEqual(inserted, 1)
        self.assertEqual(total, 2)
        
        records = self.session.query(AttendanceRecord).filter_by(zk_user_id="100").filter(AttendanceRecord.punch_time.like("2026-03-05%")).all()
        self.assertEqual(len(records), 1)

    def test_day_program_slot_edit_and_remove(self):
        """DAY_PROGRAM days display programmed slots; edit/remove must update the
        program AND the underlying raw record so the value really changes."""
        from contragest.core.database import AttendanceCorrectionLog
        from contragest.features.pointage.service import PointageService

        svc = PointageService(self.session)

        # Machine stores every punch as check_in (night-shift fingerprint device).
        self.session.add_all([
            AttendanceRecord(employee_id=self.emp1.id, zk_user_id="100",
                             punch_time="2026-07-08 08:21:59", punch_type="check_in",
                             machine_id=self.machine.id),
            AttendanceRecord(employee_id=self.emp1.id, zk_user_id="100",
                             punch_time="2026-07-08 20:56:52", punch_type="check_in",
                             machine_id=self.machine.id),
        ])
        self.session.add(AttendanceCorrectionLog(
            employee_id=self.emp1.id, reg_number="100", shift_date="2026-07-08",
            issue_type="DAY_PROGRAM", imputed_val="20:56:52|08:21:59|-|-",
            strategy="MANUAL", corrected_by="SYSTEM",
        ))
        self.session.commit()

        enriched = svc.get_attendance_records_enriched(start_date="2026-07-08", end_date="2026-07-08")
        self.assertEqual(enriched[0]["check_in"], "20:56:52")
        self.assertEqual(enriched[0]["check_out"], "08:21:59")

        # Remove OUT1 (08:21:59): slot cleared in program + raw record deleted.
        ok, msg = svc.delete_manual_punch("100", "2026-07-08", "check_out", slot_index=1)
        self.assertTrue(ok, msg)
        self.assertIn("08:21:59", msg)
        prog = svc._get_day_program("100", "2026-07-08")
        self.assertEqual(prog["out1"], "-")
        raw = self.session.query(AttendanceRecord).filter(
            AttendanceRecord.punch_time.like("2026-07-08%")).all()
        self.assertEqual([r.punch_time for r in raw], ["2026-07-08 20:56:52"])
        enriched = svc.get_attendance_records_enriched(start_date="2026-07-08", end_date="2026-07-08")
        self.assertEqual(enriched[0]["check_out"], "-")

        # Edit IN1 (20:56:52 -> 21:00): program + raw record both updated.
        ok, msg = svc.add_manual_punch("100", "2026-07-08", "21:00", "check_in", slot_index=1)
        self.assertTrue(ok, msg)
        prog = svc._get_day_program("100", "2026-07-08")
        self.assertEqual(prog["in1"], "21:00:00")
        raw = self.session.query(AttendanceRecord).filter(
            AttendanceRecord.punch_time.like("2026-07-08%")).all()
        self.assertEqual([r.punch_time for r in raw], ["2026-07-08 21:00:00"])

    def test_delete_manual_punch_target_time_matches_display_slot(self):
        """Deleting a punch by target_time must match the RESOLVED grid slot.

        The ZK device stores every machine punch as check_in, while the grid
        displays the 3rd punch of a day as OUT 2 (check_out). delete_manual_punch
        with target_time must resolve the display slot instead of filtering on
        the raw punch_type, otherwise deleting a machine OUT punch fails with
        "Record at ... not found" (REG 1921 drag-and-drop bug).
        """
        from contragest.core.database import AttendanceCorrectionLog, WorkSchedule
        from contragest.features.pointage.service import PointageService

        svc = PointageService(self.session)

        # "02 -> 10" schedule on the day, so 02:28 is that day's IN1.
        sched = WorkSchedule(name="02 -> 10", start_time="02:00", end_time="10:00")
        self.session.add(sched)
        self.session.commit()
        from contragest.core.database import EmployeeSchedule
        self.session.add(EmployeeSchedule(
            employee_id=self.emp1.id, schedule_id=sched.id,
            effective_date=date(2026, 8, 6)))
        self.session.add_all([
            AttendanceRecord(employee_id=self.emp1.id, zk_user_id="100",
                             punch_time="2026-08-06 02:28:13", punch_type="check_in",
                             machine_id=self.machine.id),
            AttendanceRecord(employee_id=self.emp1.id, zk_user_id="100",
                             punch_time="2026-08-06 10:50:35", punch_type="check_out",
                             machine_id=None),
            # Night-shift punch displayed as OUT 2 on 08-06, raw type check_in.
            AttendanceRecord(employee_id=self.emp1.id, zk_user_id="100",
                             punch_time="2026-08-07 00:28:43", punch_type="check_in",
                             machine_id=self.machine.id),
        ])
        self.session.commit()

        enriched = svc.get_attendance_records_enriched(
            start_date="2026-08-06", end_date="2026-08-06", reg_filter="100")
        self.assertEqual(enriched[0]["check_out_2"], "00:28:43")

        ok, msg = svc.delete_manual_punch(
            registration_number="100", punch_date="2026-08-06",
            punch_type="check_out", admin_name="boss", reason="move",
            slot_index=2, target_time="00:28:43")
        self.assertTrue(ok, msg)
        self.assertIn("00:28:43", msg)

        remaining = self.session.query(AttendanceRecord).filter(
            AttendanceRecord.employee_id == self.emp1.id).all()
        self.assertEqual([r.punch_time for r in remaining],
                         ["2026-08-06 02:28:13", "2026-08-06 10:50:35"])

    def test_add_manual_punch_night_shift_lands_on_destination_logic_day(self):
        """add_manual_punch must place a pre-04:00 punch on the requested logic day.

        The UI passes the destination display date verbatim; the service shifts
        the physical calendar date forward so the value is attributed to that
        date (the source of the REG 1921 double-bump bug).
        """
        from contragest.features.pointage.service import PointageService

        svc = PointageService(self.session)
        self.session.add(AttendanceRecord(
            employee_id=self.emp1.id, zk_user_id="100",
            punch_time="2026-07-09 03:04:47", punch_type="check_in",
            machine_id=self.machine.id))  # displayed as IN 1 on 07-08
        self.session.commit()

        ok, msg = svc.add_manual_punch(
            registration_number="100", punch_date="2026-07-09",
            punch_time="03:04:47", punch_type="check_in",
            admin_name="boss", reason="move", slot_index=1)
        self.assertTrue(ok, msg)

        # The value must display on the requested logic day (07-09)...
        enriched = svc.get_attendance_records_enriched(
            start_date="2026-07-09", end_date="2026-07-09", reg_filter="100")
        self.assertEqual(enriched[0]["check_in"], "03:04:47")

        # ...and its physical date must be bumped exactly ONCE (07-10).  A
        # double bump (UI + service) would store it on 07-11 / display 07-10.
        stored = self.session.query(AttendanceRecord).filter(
            AttendanceRecord.punch_type == "check_in",
            AttendanceRecord.machine_id.is_(None),
        ).all()
        self.assertEqual([r.punch_time for r in stored], ["2026-07-10 03:04:47"])

if __name__ == "__main__":
    unittest.main()

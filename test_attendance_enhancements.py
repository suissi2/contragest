"""
Unit tests — verify attendance UI enhancements (filters, enriched dicts, backup)
"""
import sys
import unittest
from datetime import date
from unittest.mock import MagicMock

sys.path.insert(0, ".")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from contragest.core.database import Base, Employee, AttendanceRecord, AttendanceRecordBackup, Department

def _make_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()

class TestAttendanceEnhancements(unittest.TestCase):
    def setUp(self):
        self.session = _make_session()
        self.dept = Department(name="IT")
        self.session.add(self.dept)
        self.session.commit()

        self.emp1 = Employee(first_name="Alice", last_name="Smith", registration_number="100", department_id=self.dept.id, role_title="Dev")
        self.emp2 = Employee(first_name="Bob", last_name="Jones", registration_number="200", department_id=self.dept.id, role_title="QA")
        self.session.add_all([self.emp1, self.emp2])
        self.session.commit()

        self.rec1 = AttendanceRecord(employee_id=self.emp1.id, zk_user_id="100", punch_time="2026-03-01 08:00:00", punch_type="check_in")
        self.rec2 = AttendanceRecord(employee_id=self.emp2.id, zk_user_id="200", punch_time="2026-03-01 17:00:00", punch_type="check_out")
        self.rec3 = AttendanceRecord(employee_id=None, zk_user_id="999", punch_time="2026-03-02 09:00:00", punch_type="check_in")
        self.session.add_all([self.rec1, self.rec2, self.rec3])
        self.session.commit()

    def tearDown(self):
        self.session.close()

    def test_filters(self):
        from contragest.features.pointage.service import PointageService
        svc = PointageService(self.session)
        # 1. Name filter
        recs = svc.get_attendance_records(name_filter="Alice")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].id, self.rec1.id)

        # 2. Reg filter
        recs = svc.get_attendance_records(reg_filter="999")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].id, self.rec3.id)
        
        # 3. Punch type filter
        recs = svc.get_attendance_records(punch_type="check_out")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].id, self.rec2.id)

        # 4. Date filter (starts with 2026-03-02)
        recs = svc.get_attendance_records(start_date="2026-03-02", end_date="2026-03-02")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0].id, self.rec3.id)

    def test_enriched_records(self):
        from contragest.features.pointage.service import PointageService
        svc = PointageService(self.session)
        enriched = svc.get_attendance_records_enriched()
        self.assertEqual(len([r for r in enriched if r["id"] != -1]), 3)
        # Check emp1 (has all fields)
        emp1_dict = next(r for r in enriched if r["id"] == self.rec1.id)
        self.assertEqual(emp1_dict["department"], "IT")
        self.assertEqual(emp1_dict["role_title"], "Dev")
        self.assertEqual(emp1_dict["reg_number"], "100")
        
        # Check orphan record
        orphan_dict = next(r for r in enriched if r["id"] == self.rec3.id)
        self.assertEqual(orphan_dict["employee"], "REG 999")
        self.assertEqual(orphan_dict["department"], "—")
        self.assertEqual(orphan_dict["role_title"], "—")
        self.assertEqual(orphan_dict["reg_number"], "999")

    def test_backup(self):
        from contragest.features.pointage.service import PointageService
        svc = PointageService(self.session)
        res = svc.backup_attendance_records("TestBackup")
        count = res[0] if isinstance(res, tuple) else res
        self.assertEqual(count, 3)
        
        backups = self.session.query(AttendanceRecordBackup).all()
        self.assertEqual(len(backups), 3)
        self.assertEqual(backups[0].backup_label, "TestBackup")
        
        source_ids = {b.source_record_id for b in backups}
        self.assertEqual(source_ids, {self.rec1.id, self.rec2.id, self.rec3.id})

    def test_public_holidays_and_jf_jfb_status(self):
        from contragest.features.pointage.service import PointageService
        from contragest.core.database import PublicHoliday, AttendanceCorrectionLog
        svc = PointageService(self.session)
        
        # 1. Create a public holiday on 2026-03-01 and 2026-03-02
        svc.save_public_holiday({"date": "2026-03-01", "name": "Holiday 1", "description": "National Holiday"})
        svc.save_public_holiday({"date": "2026-03-02", "name": "Holiday 2", "description": "National Holiday"})
        
        holidays = svc.get_public_holidays(2026)
        self.assertEqual(len(holidays), 2)
        
        # 2. Enriched status check:
        # On 2026-03-01:
        # - Alice (emp1) has check-in -> JFB
        # - Bob (emp2) has check-out -> JFB
        # On 2026-03-02:
        # - Bob has no punches -> JF
        enriched = svc.get_attendance_records_enriched(start_date="2026-03-01", end_date="2026-03-02")
        
        alice_recs_01 = [r for r in enriched if r["reg_number"] == "100" and r["raw_date"] == "2026-03-01"]
        bob_recs_01 = [r for r in enriched if r["reg_number"] == "200" and r["raw_date"] == "2026-03-01"]
        bob_recs_02 = [r for r in enriched if r["reg_number"] == "200" and r["raw_date"] == "2026-03-02"]
        
        self.assertTrue(any(r["status"] == "JFB" for r in alice_recs_01))
        self.assertTrue(any(r["status"] == "JFB" for r in bob_recs_01))
        self.assertTrue(any(r["status"] == "JF" for r in bob_recs_02))
        
        # Test Weekly Day Off precedence over Public Holiday:
        # If Bob has weekly_day_off set to SUNDAY, and 2026-03-01 is a Sunday:
        self.emp2.weekly_day_off = "SUNDAY"
        self.session.commit()
        
        enriched_rh_test = svc.get_attendance_records_enriched(start_date="2026-03-01", end_date="2026-03-01")
        bob_recs_rh = [r for r in enriched_rh_test if r["reg_number"] == "200"]
        # Bob has punches on 2026-03-01, so he should be RHB instead of JFB
        self.assertTrue(any(r["status"] == "RHB" for r in bob_recs_rh))
        
        # Revert weekly day off to not affect subsequent assertions
        self.emp2.weekly_day_off = None
        self.session.commit()
        
        # 3. Test Manual status override: A manual correction on a holiday overrides JF/JFB
        corr = AttendanceCorrectionLog(
            employee_id=self.emp2.id,
            shift_date="2026-03-02",
            issue_type="DAY_STATUS",
            imputed_val="AB",
            strategy="MANUAL"
        )
        self.session.add(corr)
        self.session.commit()
        
        # Re-fetch and verify Bob is now AB instead of JF on 2026-03-02
        enriched_after = svc.get_attendance_records_enriched(start_date="2026-03-02", end_date="2026-03-02")
        bob_recs_after = [r for r in enriched_after if r["reg_number"] == "200"]
        self.assertTrue(any(r["status"] == "AB" for r in bob_recs_after))
        
        # 4. Delete public holidays
        for h in holidays:
            svc.delete_public_holiday(h.id)
        self.assertEqual(len(svc.get_public_holidays(2026)), 0)

if __name__ == "__main__":
    unittest.main()

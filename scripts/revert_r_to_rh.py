from contragest.core.database import SessionLocal, DayStatus, DailyAttendance, AttendanceCorrectionLog

session = SessionLocal()
try:
    # 1. Update DayStatus table
    s = session.query(DayStatus).filter_by(code='R').first()
    if s:
        s.code = 'RH'
        print(f"Updated DayStatus: {s.name} from R back to RH")
    else:
        print("DayStatus 'R' not found (maybe already 'RH'?)")
    
    # 2. Update DailyAttendance
    n_att = session.query(DailyAttendance).filter_by(status='R').update({'status': 'RH'})
    print(f"Updated {n_att} records in DailyAttendance")
    
    # 3. Update AttendanceCorrectionLog
    n_corr = session.query(AttendanceCorrectionLog).filter_by(imputed_val='R').update({'imputed_val': 'RH'})
    print(f"Updated {n_corr} records in AttendanceCorrectionLog")
    
    session.commit()
    print("Changes committed successfully.")
except Exception as e:
    session.rollback()
    print(f"Error during revert: {e}")
finally:
    session.close()

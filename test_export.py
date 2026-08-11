import os
import pandas as pd
from contragest.features.pointage.export_reports import generate_attendance_excel

def test_excel_export():
    # Mock data based on the structure expected in generate_attendance_excel
    mock_data = [
        {
            'employee': 'SMITH John',
            'reg_number': '101',
            'department': 'Engineering',
            'date': '2023-10-25',
            'status': 'Present',
            'check_in': '08:00:00',
            'check_out': '12:00:00',
            'check_in_2': '13:00:00',
            'check_out_2': '17:00:00',
            'attendance_time': '08:00',
            'work_time': '08:00',
            'note': 'On time'
        },
        {
            'employee': 'DOE Jane',
            'reg_number': '102',
            'department': 'Marketing',
            'date': '2023-10-25',
            'status': 'Present',
            'check_in': '09:00:00',
            'check_out': '13:00:00',
            'check_in_2': '—',
            'check_out_2': '—',
            'attendance_time': '04:00',
            'work_time': '04:00',
            'note': 'Half day'
        }
    ]
    
    output_filepath = 'test_export_output.xlsx'
    
    try:
        generate_attendance_excel(mock_data, output_filepath, from_date='2023-10-01', to_date='2023-10-31')
        print(f"Excel export generated successfully at {output_filepath}")
        
        # Basic sanity check that file exists and is not empty
        if os.path.exists(output_filepath) and os.path.getsize(output_filepath) > 0:
            print("Verified: File exists and has content.")
        else:
            print("Error: File was not created or is empty.")
            
    except Exception as e:
        print(f"Error generating Excel export: {e}")
        
if __name__ == "__main__":
    test_excel_export()

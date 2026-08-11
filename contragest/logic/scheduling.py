"""
Dual-Shift Scheduling Logic Module.
Provides robust handling for multiple employee shifts, time parsing, and overlap validation.
"""

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import List, Optional, Tuple


@dataclass(order=True)
class Shift:
    """Represents a single work shift within a day."""
    name: str = field(compare=False)
    start: time
    end: time

    def __post_init__(self):
        """Basic validation for a single shift."""
        if self.start >= self.end:
            # Note: This implementation assumes shifts do not wrap around midnight.
            # Multi-day shift logic is handled separately in the core attendance log.
            raise ValueError(f"Shift '{self.name}' end time must be after start time.")

    def __str__(self):
        return f"{self.name}: {self.start.strftime('%H:%M')} - {self.end.strftime('%H:%M')}"


class EmployeeScheduleConfig:
    """Manages multiple shifts for an employee with robust validation and parsing."""

    def __init__(self, employee_name: str):
        self.employee_name = employee_name
        self.shifts: List[Shift] = []

    @staticmethod
    def parse_time(time_str: str) -> time:
        """
        Parses time strings in various formats:
        - 24-hour: '14:30', '14:30:00'
        - 12-hour: '2:30 PM', '02:30 PM', '8:00 AM'
        """
        formats = [
            "%H:%M", "%H:%M:%S",
            "%I:%M %p", "%I:%M%p",
            "%H:%M %p",  # Robustness for common typos
        ]
        
        clean_time = time_str.strip().upper()
        for fmt in formats:
            try:
                return datetime.strptime(clean_time, fmt).time()
            except ValueError:
                continue
        
        raise ValueError(f"Format not recognized for time: '{time_str}'. Use HH:MM or HH:MM AM/PM.")

    @classmethod
    def suggest_shift_mapping(cls, input_str: str) -> Optional[dict]:
        """
        Interprets a single string into a shift dictionary.
        Supports:
        - "8:00 - 17:00"
        - "8-12 and 18-22"
        - "8to12 & 18to22"
        """
        # Split by common separators
        separators = [" AND ", " & ", ","]
        normalized = input_str.strip().upper()
        
        segments = [normalized]
        for sep in separators:
            new_segments = []
            for seg in segments:
                new_segments.extend(seg.split(sep))
            segments = new_segments
            
        parsed_times = []
        for seg in segments:
            times = cls._parse_segment(seg)
            if times:
                parsed_times.extend(times)
        
        if not parsed_times:
            return None
            
        result = {}
        if len(parsed_times) >= 2:
            result["start_time"] = parsed_times[0].strftime("%H:%M")
            result["end_time"] = parsed_times[-1].strftime("%H:%M")
            
        if len(parsed_times) == 4:
            result["break_start"] = parsed_times[1].strftime("%H:%M")
            result["break_end"] = parsed_times[2].strftime("%H:%M")
        
        return result

    @classmethod
    def _parse_segment(cls, seg: str) -> List[time]:
        """Parses a segment like '8-12' or '8:30 to 17:00' into a list of times."""
        seg = seg.replace(" TO ", " - ").replace("-", " - ")
        parts = [p.strip() for p in seg.split(" - ") if p.strip()]
        
        parsed = []
        for p in parts:
            # Handle shorthand like "8" or "8H" or "8H30"
            p = p.replace("H", ":")
            if ":" not in p and len(p) <= 2:
                p = f"{p}:00"
            elif ":" not in p and len(p) > 2:
                # Handle 0830 -> 08:30
                p = p[:-2] + ":" + p[-2:]
                
            try:
                parsed.append(cls.parse_time(p))
            except ValueError:
                continue
        return parsed

    def add_shift(self, name: str, start_str: str, end_str: str) -> None:
        """Adds a new shift after validating it doesn't conflict with existing ones."""
        start = self.parse_time(start_str)
        end = self.parse_time(end_str)
        new_shift = Shift(name=name, start=start, end=end)
        
        # Check for overlaps
        for existing in self.shifts:
            # Overlap condition: (StartA < EndB) and (EndA > StartB)
            if (new_shift.start < existing.end) and (new_shift.end > existing.start):
                raise ValueError(
                    f"Conflict detected: New shift '{name}' overlaps with existing '{existing.name}' "
                    f"({existing.start.strftime('%H:%M')} - {existing.end.strftime('%H:%M')})."
                )
        
        self.shifts.append(new_shift)
        self.shifts.sort()  # Keep shifts in chronological order

    def remove_shift(self, name: str) -> bool:
        """Removes a shift by its name."""
        initial_len = len(self.shifts)
        self.shifts = [s for s in self.shifts if s.name.lower() != name.lower()]
        return len(self.shifts) < initial_len

    def get_summary(self) -> str:
        """Returns a human-readable summary of the daily schedule."""
        if not self.shifts:
            return f"No shifts assigned for {self.employee_name}."
        
        shift_details = ", ".join(str(s) for s in self.shifts)
        return f"Schedule for {self.employee_name}: {shift_details}"

    def get_total_hours(self) -> float:
        """Calculates total scheduled hours across all shifts."""
        total_seconds = 0
        for s in self.shifts:
            # Convert time to dummy datetime for subtraction
            dummy_date = datetime.now().date()
            dt_start = datetime.combine(dummy_date, s.start)
            dt_end = datetime.combine(dummy_date, s.end)
            total_seconds += (dt_end - dt_start).total_seconds()
        
        return total_seconds / 3600


# demonstration / usage example
if __name__ == "__main__":
    try:
        config = EmployeeScheduleConfig("John Doe")
        
        # Adding a morning shift (12h format)
        config.add_shift("Morning", "8:00 AM", "12:00 PM")
        
        # Adding an evening shift (24h format)
        config.add_shift("Evening", "18:00", "22:00")
        
        print(config.get_summary())
        print(f"Total Work: {config.get_total_hours()} hours")
        
        # Testing overlap validation
        print("\nAttempting to add conflicting shift...")
        config.add_shift("Middle", "11:30", "15:00")
        
    except ValueError as e:
        print(f"Validation Error: {e}")

"""
CSV & Spreadsheet Exporter
Generates CSV spreadsheets for timetable and duty rosters.
"""
import csv
from typing import Dict, List, Optional
from models.timetable_data import TimetableProject

class TimetableSpreadsheetExporter:
    def __init__(self, project: TimetableProject):
        self.project = project

    def export_master_csv(self, output_path: str):
        days = list(self.project.institution.working_days)
        periods_count = self.project.institution.periods_per_day
        sections = list(self.project.sections.values())

        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([self.project.institution.name, f"Academic Year: {self.project.institution.academic_year}"])
            writer.writerow([])

            for day in days:
                day_periods = self.project.institution.get_periods_for_day(day)
                dismissal_note = f" (Early Dismissal after Period {day_periods})" if day_periods < self.project.institution.periods_per_day else ""
                writer.writerow([f"DAY: {day.upper()}{dismissal_note}"])
                header = ["Class / Section"] + [f"Period {p}" for p in range(1, day_periods + 1)]
                writer.writerow(header)

                for sec in sections:
                    row = [sec.display_name]
                    for p in range(1, day_periods + 1):
                        slot = self.project.get_slot_at(day, p, sec.id)
                        if slot:
                            sub = self.project.subjects.get(slot.subject_id)
                            teacher = self.project.teachers.get(slot.teacher_id)
                            room = self.project.classrooms.get(slot.room_id)
                            sub_name = sub.code if sub else slot.subject_id
                            t_code = teacher.code if teacher else ""
                            r_name = room.name if room else ""
                            row.append(f"{sub_name} ({t_code}) [{r_name}]")
                        else:
                            row.append("—")
                    writer.writerow(row)
                writer.writerow([])

    def export_duty_roster_csv(self, output_path: str):
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([self.project.institution.name, "Staff Duty & Invigilation Roster"])
            writer.writerow([])
            writer.writerow(["Day", "Period / Slot", "Duty Name", "Campus Location", "Assigned Teacher ID", "Assigned Teacher Name"])

            days_order = {d: i for i, d in enumerate(self.project.institution.working_days)}
            sorted_duties = sorted(self.project.duty_assignments, key=lambda d: (days_order.get(d.day, 99), d.period))

            for d in sorted_duties:
                time_lbl = d.time_label or (f"Period {d.period}" if d.period > 0 else "Morning")
                writer.writerow([d.day, time_lbl, d.duty_name, d.location, d.teacher_id, d.teacher_name])

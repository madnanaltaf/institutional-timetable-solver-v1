"""
Comprehensive Automated Test Suite for Timetable & Duty Roster Constraint Solver
"""
import unittest
import os
import tempfile
from models.timetable_data import TimetableProject
from models.lesson import LessonAllocation
from models.teacher import Teacher
from solver.timetable_solver import TimetableSolver
from solver.duty_solver import DutyRosterSolver
from solver.validator import ProjectValidator
from exports.pdf_generator import TimetablePDFGenerator
from exports.excel_exporter import TimetableSpreadsheetExporter

class TestTimetableSolver(unittest.TestCase):
    def setUp(self):
        self.project = TimetableProject.create_sample_institution()

    def test_preflight_validator_clean(self):
        """Tests that sample institution passes validation with zero errors."""
        validator = ProjectValidator(self.project)
        issues = validator.validate()
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertEqual(len(errors), 0, f"Expected 0 errors, got: {errors}")

    def test_preflight_validator_detects_overbooking(self):
        """Tests that validator catches when a section requests more periods than available in the week."""
        total_slots = len(self.project.institution.working_days) * self.project.institution.periods_per_day
        # Add excessive allocation
        bad_l = LessonAllocation(
            id="L_EXCESS",
            section_id="s_10a",
            subject_id="sub_math",
            teacher_id="t_turing",
            periods_per_week=total_slots + 5
        )
        self.project.lessons[bad_l.id] = bad_l

        validator = ProjectValidator(self.project)
        issues = validator.validate()
        errors = [i for i in issues if i.severity == "ERROR"]
        self.assertTrue(any("Over-allocation" in e.title for e in errors))

    def test_timetable_solver_hard_constraints(self):
        """Tests that solver satisfies 100% of hard constraints."""
        solver = TimetableSolver(self.project, timeout_seconds=15.0)
        res = solver.solve()
        self.assertTrue(res.success, f"Solver failed: {res.message}")
        self.project.schedule = res.schedule

        # Check: No teacher double-booking
        teacher_slots = set()
        for s in self.project.schedule:
            for p_off in range(s.duration):
                slot_p = s.period + p_off
                key = (s.day, slot_p, s.teacher_id)
                self.assertNotIn(key, teacher_slots, f"Teacher double booked: {key}")
                teacher_slots.add(key)

        # Check: No section double-booking
        sec_slots = set()
        for s in self.project.schedule:
            for p_off in range(s.duration):
                slot_p = s.period + p_off
                key = (s.day, slot_p, s.section_id)
                self.assertNotIn(key, sec_slots, f"Section double booked: {key}")
                sec_slots.add(key)

        # Check: No room double-booking
        room_slots = set()
        for s in self.project.schedule:
            if s.room_id:
                for p_off in range(s.duration):
                    slot_p = s.period + p_off
                    key = (s.day, slot_p, s.room_id)
                    self.assertNotIn(key, room_slots, f"Room double booked: {key}")
                    room_slots.add(key)

        # Check: Teacher unavailabilities respected
        for s in self.project.schedule:
            t = self.project.teachers.get(s.teacher_id)
            if t:
                for p_off in range(s.duration):
                    self.assertTrue(
                        t.is_available(s.day, s.period + p_off),
                        f"Teacher {t.name} scheduled during unavailable slot {s.day} P{s.period + p_off}"
                    )

        # Check: Recess break not crossed by multi-period blocks
        b_after = self.project.institution.break_after_period
        for s in self.project.schedule:
            if s.duration > 1:
                self.assertFalse(
                    s.period <= b_after < s.period + s.duration,
                    f"Slot {s.id} spans across recess break at period {b_after}"
                )

    def test_synchronized_science_practicals_alignment(self):
        """
        Tests critical requirement:
        Aligned practicals across sections must occur at the exact same (day, period).
        """
        solver = TimetableSolver(self.project, timeout_seconds=15.0)
        res = solver.solve()
        self.assertTrue(res.success)
        self.project.schedule = res.schedule

        sync_groups = {}
        for s in self.project.schedule:
            if s.sync_group_id:
                sync_groups.setdefault(s.sync_group_id, []).append(s)

        self.assertGreater(len(sync_groups), 0, "No synchronized practicals found in schedule")

        for sg_id, slots in sync_groups.items():
            first_day = slots[0].day
            first_period = slots[0].period
            for s in slots:
                self.assertEqual(
                    s.day, first_day,
                    f"Sync group {sg_id} mismatch in day: {s.day} vs {first_day}"
                )
                self.assertEqual(
                    s.period, first_period,
                    f"Sync group {sg_id} mismatch in period: P{s.period} vs P{first_period}"
                )

    def test_duty_roster_fairness_and_no_teaching_conflict(self):
        """Tests that duty roster balances workload fairly and never conflicts with teaching."""
        solver = TimetableSolver(self.project, timeout_seconds=15.0)
        res = solver.solve()
        self.project.schedule = res.schedule

        duty_solver = DutyRosterSolver(self.project)
        d_res = duty_solver.solve()
        self.assertTrue(d_res.success)
        self.project.duty_assignments = d_res.assignments

        # 1. No conflict with teaching
        teaching_set = set()
        for s in self.project.schedule:
            for p_off in range(s.duration):
                teaching_set.add((s.teacher_id, s.day, s.period + p_off))

        for d in self.project.duty_assignments:
            if d.period > 0:
                self.assertNotIn(
                    (d.teacher_id, d.day, d.period),
                    teaching_set,
                    f"Duty conflict: Teacher {d.teacher_name} has class on {d.day} P{d.period}"
                )

        # 2. Fairness range
        counts = d_res.stats["teacher_duty_counts"]
        spread = max(counts.values()) - min(counts.values())
        self.assertLessEqual(spread, 2, f"Duty spread too uneven: {counts}")

    def test_pdf_and_csv_generation(self):
        """Tests that all 5 PDF exports and CSV exports generate non-empty valid files."""
        solver = TimetableSolver(self.project, timeout_seconds=15.0)
        res = solver.solve()
        self.project.schedule = res.schedule

        duty_solver = DutyRosterSolver(self.project)
        d_res = duty_solver.solve()
        self.project.duty_assignments = d_res.assignments

        with tempfile.TemporaryDirectory() as tmp_dir:
            pdf_gen = TimetablePDFGenerator(self.project)
            p_sec = os.path.join(tmp_dir, "Sections.pdf")
            p_teach = os.path.join(tmp_dir, "Teachers.pdf")
            p_sub = os.path.join(tmp_dir, "Subjects.pdf")
            p_master = os.path.join(tmp_dir, "Master.pdf")
            p_duty = os.path.join(tmp_dir, "Duty.pdf")

            pdf_gen.export_section_timetables_pdf(p_sec)
            pdf_gen.export_teacher_timetables_pdf(p_teach)
            pdf_gen.export_subject_schedules_pdf(p_sub)
            pdf_gen.export_master_timetable_pdf(p_master)
            pdf_gen.export_duty_roster_pdf(p_duty)

            for p in [p_sec, p_teach, p_sub, p_master, p_duty]:
                self.assertTrue(os.path.exists(p), f"PDF not created: {p}")
                self.assertGreater(os.path.getsize(p), 1000, f"PDF file too small: {p}")

            csv_gen = TimetableSpreadsheetExporter(self.project)
            c_master = os.path.join(tmp_dir, "Master.csv")
            c_duty = os.path.join(tmp_dir, "Duty.csv")
            csv_gen.export_master_csv(c_master)
            csv_gen.export_duty_roster_csv(c_duty)

            self.assertTrue(os.path.exists(c_master) and os.path.getsize(c_master) > 100)
            self.assertTrue(os.path.exists(c_duty) and os.path.getsize(c_duty) > 100)

    def test_friday_reduced_periods_constraint(self):
        """Tests that solver strictly respects Friday reduced periods (e.g. 4 periods max)."""
        self.project.institution.periods_per_day = 7
        self.project.institution.friday_periods = 4
        self.project.institution.day_periods = {"Friday": 4}

        expected_total = 4 * 7 + 4  # 32 slots
        self.assertEqual(self.project.institution.get_total_weekly_slots(), expected_total)
        self.assertEqual(self.project.institution.get_periods_for_day("Friday"), 4)
        self.assertEqual(self.project.institution.get_periods_for_day("Monday"), 7)

        solver = TimetableSolver(self.project, timeout_seconds=15.0)
        res = solver.solve()
        self.assertTrue(res.success, f"Solver failed: {res.message}")

        # Check every scheduled slot: If scheduled on Friday, slot + duration - 1 <= 4
        for slot in res.schedule:
            if slot.day == "Friday":
                end_p = slot.period + slot.duration - 1
                self.assertLessEqual(
                    end_p, 4,
                    f"Slot on Friday exceeded Friday limit of 4 periods: {slot.id} ended at period {end_p}"
                )

    def test_single_subject_specialist_and_class_incharge(self):
        """Tests single subject specialist assignment and designated Class Incharge."""
        # 1. Single subject specialist
        t = Teacher(id="t_spec_1", name="Dr. Specialist", code="DSP")
        t.set_single_subject("sub_phy")
        self.assertEqual(t.primary_subject_id, "sub_phy")
        self.assertTrue(t.teaches_subject("sub_phy"))
        self.assertFalse(t.teaches_subject("sub_chem"))

        # 2. Class Teacher / Incharge assignment
        sec = self.project.sections["s_10a"]
        sec.class_teacher_id = "t_newton"
        self.assertEqual(sec.class_teacher_id, "t_newton")

        # Serialized and restored without data loss
        sec_dict = sec.to_dict()
        self.assertEqual(sec_dict["class_teacher_id"], "t_newton")
        from models.section import Section
        restored_sec = Section.from_dict(sec_dict)
        self.assertEqual(restored_sec.class_teacher_id, "t_newton")

if __name__ == "__main__":
    unittest.main()

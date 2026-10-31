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

    def test_master_matrices_by_day_and_margins(self):
        """Tests that day-by-day master matrices generate with 1 page per day and guaranteed A4 margins."""
        solver = TimetableSolver(self.project, timeout_seconds=15.0)
        res = solver.solve()
        self.assertTrue(res.success)
        self.project.schedule = res.schedule

        duty_solver = DutyRosterSolver(self.project)
        duty_res = duty_solver.solve()
        self.assertTrue(duty_res.success)

        import pymupdf
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_gen = TimetablePDFGenerator(self.project)

            # 1. Section matrix by day
            p_sec_matrix = os.path.join(tmpdir, "Sections_Matrix.pdf")
            pdf_gen.export_master_sections_matrix_by_day_pdf(p_sec_matrix)
            doc_sec = pymupdf.open(p_sec_matrix)
            self.assertEqual(len(doc_sec), len(self.project.institution.working_days), "Expected 1 page per day in Master Section Matrix")
            # Verify margins
            p0 = doc_sec[0]
            rects = [block[:4] for block in p0.get_text('blocks')]
            min_x = min(r[0] for r in rects)
            max_x = max(r[2] for r in rects)
            self.assertGreater(min_x, 25.0, f"Left margin too small: {min_x}")
            self.assertGreater(p0.rect.width - max_x, 25.0, f"Right margin too small: {p0.rect.width - max_x}")
            doc_sec.close()

            # 2. Faculty matrix by day
            p_fac_matrix = os.path.join(tmpdir, "Faculty_Matrix.pdf")
            pdf_gen.export_master_faculty_matrix_by_day_pdf(p_fac_matrix)
            doc_fac = pymupdf.open(p_fac_matrix)
            self.assertGreaterEqual(len(doc_fac), len(self.project.institution.working_days))
            doc_fac.close()

            # 3. Class booklet margins
            p_booklet = os.path.join(tmpdir, "Class_Booklet.pdf")
            pdf_gen.export_section_timetables_pdf(p_booklet)
            doc_book = pymupdf.open(p_booklet)
            self.assertEqual(len(doc_book), len(self.project.sections))
            p_b0 = doc_book[0]
            b_rects = [block[:4] for block in p_b0.get_text('blocks')]
            b_min_x = min(r[0] for r in b_rects)
            b_max_x = max(r[2] for r in b_rects)
            self.assertGreater(b_min_x, 25.0, f"Class booklet left margin too small: {b_min_x}")
            self.assertGreater(p_b0.rect.width - b_max_x, 25.0, f"Class booklet right margin too small: {p_b0.rect.width - b_max_x}")
            doc_book.close()

    def test_grade_9_10_11_12_parallel_pairing(self):
        """Tests that 9C CS <-> 9B Bio, 10C CS <-> 10B Bio, 11C CS <-> 11B Chem, 12C CS <-> 12B Chem are paired."""
        proj = TimetableProject.load_from_file("sample_data/college_sample.json")
        solver = TimetableSolver(proj, timeout_seconds=15.0)
        res = solver.solve()
        self.assertTrue(res.success)

        def get_slots(sec_id, sub_id):
            return [(s.day, s.period) for s in res.schedule if s.section_id == sec_id and s.subject_id == sub_id and s.sync_group_id]

        # 9C CS & 9B Bio
        cs_9c = get_slots("s_9c", "sub_cs")
        bio_9b = get_slots("s_9b", "sub_bio")
        self.assertEqual(len(cs_9c), 2)
        self.assertEqual(sorted(cs_9c), sorted(bio_9b))

        # 10C CS & 10B Bio
        cs_10c = get_slots("s_10c", "sub_cs")
        bio_10b = get_slots("s_10b", "sub_bio")
        self.assertEqual(len(cs_10c), 2)
        self.assertEqual(sorted(cs_10c), sorted(bio_10b))

        # 11C CS & 11B Chem
        cs_11c = get_slots("s_11c", "sub_cs")
        chem_11b = get_slots("s_11b", "sub_chem")
        self.assertEqual(len(cs_11c), 2)
        self.assertEqual(sorted(cs_11c), sorted(chem_11b))

        # 12C CS & 12B Chem
        cs_12c = get_slots("s_12c", "sub_cs")
        chem_12b = get_slots("s_12b", "sub_chem")
        self.assertEqual(len(cs_12c), 2)
        self.assertEqual(sorted(cs_12c), sorted(chem_12b))

    def test_combined_all_sections_sessions_same_time(self):
        """All-sections lessons (C.O counselling) must appear in every section of a class at one time."""
        proj = TimetableProject.load_from_file("sample_data/college_sample.json")
        solver = TimetableSolver(proj, timeout_seconds=30.0)
        res = solver.solve()
        self.assertTrue(res.success, f"Solver failed: {res.message}")

        groups = {}
        for s in res.schedule:
            if s.combined_group_id:
                groups.setdefault(s.combined_group_id, []).append(s)

        self.assertEqual(
            {g.replace("COMB_CO_", "") for g in groups},
            {str(grade) for grade in range(6, 13)},
            f"Expected combined C.O sessions for grades 6-12, got {sorted(groups)}"
        )

        for gid, slots in groups.items():
            sections = {s.section_id for s in slots}
            times = {(s.day, s.period) for s in slots}
            self.assertEqual(len(times), 1, f"{gid} was split across times: {times}")
            self.assertEqual(len({s.teacher_id for s in slots}), 1, f"{gid} uses multiple teachers")
            self.assertTrue(all(s.all_sections for s in slots), f"{gid} missing all_sections flag")

            class_id = proj.sections[next(iter(sections))].class_id
            expected = {sec.id for sec in proj.sections.values() if sec.class_id == class_id}
            self.assertEqual(sections, expected, f"{gid} does not cover every section of the class")

            # Alignment group helper used by manual move/swap must see the whole session
            self.assertEqual(len(proj.get_alignment_group(slots[0])), len(slots))

    def test_cross_grade_four_way_alignment(self):
        """9C/10C CS must run simultaneously with 9B/10B Bio, and 11C/12C CS with 11B/12B Chem."""
        proj = TimetableProject.load_from_file("sample_data/college_sample.json")
        solver = TimetableSolver(proj, timeout_seconds=30.0)
        res = solver.solve()
        self.assertTrue(res.success, f"Solver failed: {res.message}")

        aligned = {}
        for s in res.schedule:
            if s.sync_group_id:
                aligned.setdefault(s.sync_group_id, []).append(s)

        expected_groups = {
            "ALIGN_09_10_BIO_CS": {
                "s_9b": "sub_bio", "s_9c": "sub_cs",
                "s_10b": "sub_bio", "s_10c": "sub_cs",
            },
            "ALIGN_11_12_CHEM_CS": {
                "s_11b": "sub_chem", "s_11c": "sub_cs",
                "s_12b": "sub_chem", "s_12c": "sub_cs",
            },
        }

        for gid, expected_sections in expected_groups.items():
            self.assertIn(gid, aligned, f"Missing alignment group {gid}")
            slots = aligned[gid]
            times = {(s.day, s.period) for s in slots}
            self.assertEqual(len(times), 2, f"{gid} should meet twice a week, got {times}")

            by_section = {}
            for s in slots:
                self.assertEqual(s.subject_id, expected_sections[s.section_id])
                by_section.setdefault(s.section_id, set()).add((s.day, s.period))
            self.assertEqual(set(by_section), set(expected_sections))
            for sec_id, sec_times in by_section.items():
                self.assertEqual(sec_times, times, f"{gid}: {sec_id} is not aligned with the group")

    def test_validate_schedule_allows_combined_but_flags_conflicts(self):
        """validate_schedule() accepts shared combined sessions yet catches real double-bookings."""
        proj = TimetableProject.load_from_file("sample_data/college_sample.json")
        solver = TimetableSolver(proj, timeout_seconds=30.0)
        res = solver.solve()
        self.assertTrue(res.success, f"Solver failed: {res.message}")
        proj.schedule = res.schedule

        errors = [i for i in ProjectValidator(proj).validate_schedule() if i.severity == "ERROR"]
        self.assertEqual(errors, [], f"Valid schedule reported conflicts: {[e.title for e in errors]}")

        # Strip the combined tag from one member: the shared teacher is now a genuine clash.
        victim = next(s for s in proj.schedule if s.combined_group_id)
        victim.combined_group_id = ""
        victim.all_sections = False
        errors = [i for i in ProjectValidator(proj).validate_schedule() if i.severity == "ERROR"]
        self.assertTrue(
            any("Teacher Double Booked" in e.title for e in errors),
            f"Expected teacher double-booking after breaking a combined group, got {[e.title for e in errors]}"
        )

    def test_manual_slot_locking_and_persistence(self):
        """Tests that locked slots are never moved or overwritten by the solver."""
        proj = TimetableProject.load_from_file("sample_data/college_sample.json")
        slot_to_lock = [s for s in proj.schedule if s.section_id == "s_10a"][0]
        orig_day, orig_period = slot_to_lock.day, slot_to_lock.period
        slot_to_lock.is_locked = True

        solver = TimetableSolver(proj, timeout_seconds=15.0)
        res = solver.solve()
        self.assertTrue(res.success)

        # Confirm locked slot was preserved
        locked_found = [s for s in res.schedule if s.id == slot_to_lock.id]
        self.assertEqual(len(locked_found), 1)
        self.assertEqual(locked_found[0].day, orig_day)
        self.assertEqual(locked_found[0].period, orig_period)
        self.assertTrue(locked_found[0].is_locked)

if __name__ == "__main__":
    unittest.main()

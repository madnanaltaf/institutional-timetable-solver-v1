"""
Pre-Flight Feasibility & Diagnostic Validator
Performs fast mathematical checks before running the solver to identify impossible
allocations, room bottlenecks, teacher overbooking, or curriculum mismatches.
"""
from typing import List, Dict, Tuple, Any
from models.timetable_data import TimetableProject

class ValidationIssue:
    def __init__(self, severity: str, title: str, description: str, entity_type: str = "", entity_id: str = ""):
        self.severity = severity  # "ERROR", "WARNING", "INFO"
        self.title = title
        self.description = description
        self.entity_type = entity_type
        self.entity_id = entity_id

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id
        }


class ProjectValidator:
    def __init__(self, project: TimetableProject):
        self.project = project

    def validate(self) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        days_count = len(self.project.institution.working_days)
        periods_per_day = self.project.institution.periods_per_day
        total_weekly_slots = self.project.institution.get_total_weekly_slots()

        if days_count == 0:
            issues.append(ValidationIssue(
                "ERROR", "No Working Days Configured",
                "Please configure at least one working day in Institution Settings."
            ))
            return issues

        if periods_per_day == 0:
            issues.append(ValidationIssue(
                "ERROR", "No Periods Configured",
                "Periods per day must be at least 1."
            ))
            return issues

        # 1. Section Load Check
        section_periods: Dict[str, int] = {}
        for lesson in self.project.lessons.values():
            section_periods[lesson.section_id] = section_periods.get(lesson.section_id, 0) + lesson.periods_per_week

        for sec_id, total_p in section_periods.items():
            sec = self.project.sections.get(sec_id)
            sec_name = sec.display_name if sec else sec_id
            if total_p > total_weekly_slots:
                issues.append(ValidationIssue(
                    "ERROR", f"Section Over-allocation: {sec_name}",
                    f"Section requires {total_p} periods per week, but only {total_weekly_slots} slots exist ({days_count} days x {periods_per_day} periods).",
                    "Section", sec_id
                ))
            elif total_p > total_weekly_slots * 0.95:
                issues.append(ValidationIssue(
                    "WARNING", f"Section High Density: {sec_name}",
                    f"Section is {total_p}/{total_weekly_slots} slots filled. Little or no free study periods remaining.",
                    "Section", sec_id
                ))

        # 2. Teacher Load Check
        # Combined all-sections sessions are taught once, so count the group once.
        teacher_periods: Dict[str, int] = {}
        counted_combined: set = set()
        for lesson in self.project.lessons.values():
            if lesson.combined_group_id:
                if lesson.combined_group_id in counted_combined:
                    continue
                counted_combined.add(lesson.combined_group_id)
            teacher_periods[lesson.teacher_id] = teacher_periods.get(lesson.teacher_id, 0) + lesson.periods_per_week

        for teacher_id, total_p in teacher_periods.items():
            teacher = self.project.teachers.get(teacher_id)
            if not teacher:
                issues.append(ValidationIssue(
                    "ERROR", "Missing Teacher Reference",
                    f"A lesson references non-existent teacher ID '{teacher_id}'.",
                    "Teacher", teacher_id
                ))
                continue

            available_slots_count = total_weekly_slots - len(teacher.unavailable_slots)
            if total_p > available_slots_count:
                issues.append(ValidationIssue(
                    "ERROR", f"Teacher Overbooked: {teacher.name}",
                    f"Teacher assigned {total_p} periods, but only {available_slots_count} slots are available due to unavailabilities.",
                    "Teacher", teacher_id
                ))
            elif total_p > teacher.max_periods_per_week:
                issues.append(ValidationIssue(
                    "WARNING", f"Exceeds Max Weekly Workload: {teacher.name}",
                    f"Teacher assigned {total_p} periods, exceeding preferred max of {teacher.max_periods_per_week}.",
                    "Teacher", teacher_id
                ))

            # Daily theoretical max
            if total_p > teacher.max_periods_per_day * days_count:
                issues.append(ValidationIssue(
                    "WARNING", f"Daily Workload Exceeded: {teacher.name}",
                    f"Total load {total_p} exceeds preferred daily capacity across {days_count} days ({days_count} x {teacher.max_periods_per_day} = {teacher.max_periods_per_day * days_count}). Solver will balance this as soft optimization.",
                    "Teacher", teacher_id
                ))

        # 3. Combined All-Sections Session Consistency Check
        combined_groups: Dict[str, List[str]] = {}
        for lesson in self.project.lessons.values():
            if lesson.combined_group_id:
                combined_groups.setdefault(lesson.combined_group_id, []).append(lesson.id)

        for cg_id, l_ids in combined_groups.items():
            lessons = [self.project.lessons[lid] for lid in l_ids]
            first = lessons[0]
            first_sec = self.project.sections.get(first.section_id)
            class_sections = {
                s.id for s in self.project.sections.values()
                if first_sec and s.class_id == first_sec.class_id
            }

            if len(lessons) < 2:
                issues.append(ValidationIssue(
                    "WARNING", f"Incomplete Combined Session: {cg_id}",
                    "A combined all-sections session needs a row for every section of the class. "
                    "Tick 'All sections' again to recreate the missing rows.",
                    "Lesson", first.id
                ))

            sections_in_group = set()
            for l in lessons:
                if l.section_id in sections_in_group:
                    issues.append(ValidationIssue(
                        "ERROR", f"Duplicate Section in Combined Session: {cg_id}",
                        f"Section '{l.section_id}' appears multiple times in the same combined session.",
                        "Lesson", l.id
                    ))
                sections_in_group.add(l.section_id)

                if l.block_size != first.block_size:
                    issues.append(ValidationIssue(
                        "ERROR", f"Mismatched Block Size in Combined Session: {cg_id}",
                        f"Every section of a combined session must use the same block size "
                        f"({l.block_size} vs {first.block_size}).",
                        "Lesson", l.id
                    ))
                if l.subject_id != first.subject_id:
                    issues.append(ValidationIssue(
                        "ERROR", f"Different Subjects in Combined Session: {cg_id}",
                        "Every section of a combined session must take the same subject.",
                        "Lesson", l.id
                    ))
                if l.teacher_id != first.teacher_id:
                    issues.append(ValidationIssue(
                        "ERROR", f"Different Teachers in Combined Session: {cg_id}",
                        "A combined all-sections session must have the same teacher in every section.",
                        "Lesson", l.id
                    ))
                if l.periods_per_week != first.periods_per_week:
                    issues.append(ValidationIssue(
                        "WARNING", f"Mismatched Weekly Periods in Combined Session: {cg_id}",
                        "Sections of a combined session should have the same periods per week.",
                        "Lesson", l.id
                    ))
                if l.sync_group_id:
                    issues.append(ValidationIssue(
                        "WARNING", f"Combined Lesson Also Tagged for Sync: {l.id}",
                        "A combined all-sections lesson cannot also join a synchronized practical group.",
                        "Lesson", l.id
                    ))

            if class_sections and class_sections - sections_in_group:
                missing = sorted(
                    (self.project.sections[sid].display_name if sid in self.project.sections else sid)
                    for sid in class_sections - sections_in_group
                )
                issues.append(ValidationIssue(
                    "WARNING", f"Combined Session Missing Sections: {cg_id}",
                    f"Missing section(s): {', '.join(missing)}. All sections of the class should be included.",
                    "Lesson", first.id
                ))

        # 4. Synchronized Groups Consistency Check
        sync_groups: Dict[str, List[str]] = {}
        for lesson in self.project.lessons.values():
            if lesson.sync_group_id and not lesson.combined_group_id:
                sync_groups.setdefault(lesson.sync_group_id, []).append(lesson.id)

        for sg_id, l_ids in sync_groups.items():
            if len(l_ids) < 2:
                issues.append(ValidationIssue(
                    "WARNING", f"Incomplete Synchronized Group: {sg_id}",
                    f"Synchronized group '{sg_id}' has only 1 lesson. Add paired practicals to synchronize them.",
                    "Lesson", l_ids[0]
                ))
            else:
                # Check block_size matches
                first_lesson = self.project.lessons[l_ids[0]]
                sections_in_sg = set()
                teachers_in_sg = set()
                rooms_in_sg = set()
                for lid in l_ids:
                    l = self.project.lessons[lid]
                    if l.block_size != first_lesson.block_size:
                        issues.append(ValidationIssue(
                            "ERROR", f"Mismatched Block Size in Sync Group: {sg_id}",
                            f"Lessons in synchronized group must have the same block size (duration). Lesson '{l.id}' has {l.block_size} vs {first_lesson.block_size}.",
                            "Lesson", l.id
                        ))
                    if l.section_id in sections_in_sg:
                        issues.append(ValidationIssue(
                            "ERROR", f"Duplicate Section in Sync Group: {sg_id}",
                            f"Section '{l.section_id}' is assigned multiple simultaneous lessons in the same sync group.",
                            "Lesson", l.id
                        ))
                    sections_in_sg.add(l.section_id)

                    if l.teacher_id in teachers_in_sg:
                        issues.append(ValidationIssue(
                            "ERROR", f"Teacher Conflict in Sync Group: {sg_id}",
                            f"Teacher '{l.teacher_id}' is assigned to multiple simultaneous lessons in sync group '{sg_id}'.",
                            "Lesson", l.id
                        ))
                    teachers_in_sg.add(l.teacher_id)

                    if l.room_id:
                        if l.room_id in rooms_in_sg:
                            issues.append(ValidationIssue(
                                "ERROR", f"Room Conflict in Sync Group: {sg_id}",
                                f"Room '{l.room_id}' is assigned to multiple simultaneous lessons in sync group '{sg_id}'.",
                                "Lesson", l.id
                            ))
                        rooms_in_sg.add(l.room_id)

        # 5. Room Requirements & Capacity Check
        for lesson in self.project.lessons.values():
            sub = self.project.subjects.get(lesson.subject_id)
            sec = self.project.sections.get(lesson.section_id)
            if not sub or not sec:
                continue

            if lesson.room_id:
                room = self.project.classrooms.get(lesson.room_id)
                if room and room.capacity < sec.student_count:
                    issues.append(ValidationIssue(
                        "WARNING", f"Room Capacity Tight: {room.name}",
                        f"Room '{room.name}' has capacity {room.capacity}, while {sec.display_name} has {sec.student_count} students.",
                        "Room", room.id
                    ))

        return issues

    def validate_schedule(self, schedule=None) -> List[ValidationIssue]:
        """Checks a concrete schedule for hard conflicts.

        Used after manual moves/swaps and by tests. Combined all-sections sessions
        are deliberately allowed to share one teacher (and one room) simultaneously.
        """
        schedule = list(self.project.schedule if schedule is None else schedule)
        issues: List[ValidationIssue] = []
        break_after = self.project.institution.break_after_period

        for s in schedule:
            day_max = self.project.institution.get_periods_for_day(s.day)
            end_p = s.period + s.duration - 1
            if s.period < 1 or end_p > day_max:
                issues.append(ValidationIssue(
                    "ERROR", "Slot Outside Day Bounds",
                    f"{s.day} P{s.period} ({s.duration}P) exceeds the day's {day_max}-period limit.",
                    "Slot", s.id
                ))
            if s.duration > 1 and s.period <= break_after < s.period + s.duration:
                issues.append(ValidationIssue(
                    "ERROR", "Slot Crosses Recess",
                    f"A {s.duration}-period block starting at {s.day} P{s.period} crosses the recess break.",
                    "Slot", s.id
                ))
            teacher = self.project.teachers.get(s.teacher_id)
            if teacher:
                for p in range(s.period, s.period + s.duration):
                    if not teacher.is_available(s.day, p):
                        issues.append(ValidationIssue(
                            "ERROR", "Teacher Unavailable",
                            f"'{teacher.name}' is marked unavailable on {s.day} P{p}.",
                            "Slot", s.id
                        ))
                        break

        buckets = {"section_id": {}, "teacher_id": {}, "room_id": {}}
        for s in schedule:
            for p in range(s.period, s.period + s.duration):
                for entity in buckets:
                    if entity == "room_id" and not s.room_id:
                        continue
                    key = (s.day, p, getattr(s, entity))
                    buckets[entity].setdefault(key, []).append(s)

        for (day, p, sec_id), slots in buckets["section_id"].items():
            if len(slots) > 1:
                sec = self.project.sections.get(sec_id)
                issues.append(ValidationIssue(
                    "ERROR", "Section Double Booked",
                    f"{sec.display_name if sec else sec_id} has {len(slots)} lectures on {day} P{p}.",
                    "Section", sec_id
                ))

        for (day, p, teacher_id), slots in buckets["teacher_id"].items():
            if len(slots) <= 1:
                continue
            combined_keys = {(s.combined_group_id, s.subject_id) for s in slots}
            if all(s.combined_group_id for s in slots) and len(combined_keys) == 1:
                continue
            teacher = self.project.teachers.get(teacher_id)
            issues.append(ValidationIssue(
                "ERROR", "Teacher Double Booked",
                f"'{teacher.name if teacher else teacher_id}' is scheduled in "
                f"{len(slots)} places on {day} P{p}.",
                "Teacher", teacher_id
            ))

        for (day, p, room_id), slots in buckets["room_id"].items():
            if len(slots) <= 1:
                continue
            combined_keys = {s.combined_group_id for s in slots}
            if all(s.combined_group_id for s in slots) and len(combined_keys) == 1:
                continue
            room = self.project.classrooms.get(room_id)
            issues.append(ValidationIssue(
                "ERROR", "Room Double Booked",
                f"'{room.name if room else room_id}' is used by {len(slots)} lectures on {day} P{p}.",
                "Room", room_id
            ))

        return issues

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
        teacher_periods: Dict[str, int] = {}
        for lesson in self.project.lessons.values():
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

        # 3. Synchronized Groups Consistency Check
        sync_groups: Dict[str, List[str]] = {}
        for lesson in self.project.lessons.values():
            if lesson.sync_group_id:
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

        # 4. Room Requirements & Capacity Check
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

"""
Duty Roster & Invigilation Constraint Solver
Distributes exam invigilation, assembly supervision, and recess monitoring duties
fairly among teachers while strictly preventing conflicts with their teaching schedules.
"""
import uuid
import math
from typing import Dict, List, Set, Tuple, Optional, Any
from models.timetable_data import TimetableProject
from models.duty import DutyAssignment, DutySlot, DutyType
from models.lesson import ScheduledSlot

class DutySolverResult:
    def __init__(self, success: bool, message: str, assignments: List[DutyAssignment], stats: Dict[str, Any]):
        self.success = success
        self.message = message
        self.assignments = assignments
        self.stats = stats


class DutyRosterSolver:
    def __init__(self, project: TimetableProject):
        self.project = project

    def solve(self) -> DutySolverResult:
        """
        Executes fair-share optimization for all configured duty slots.
        """
        if not self.project.duty_slots:
            return DutySolverResult(
                success=True,
                message="No duty slots configured. Generated empty roster.",
                assignments=[],
                stats={"total_duties": 0}
            )

        # 1. Map teaching commitments: (teacher_id, day, period) -> True
        teaching_commitments: Set[Tuple[str, str, int]] = set()
        for s in self.project.schedule:
            for p_offset in range(s.duration):
                teaching_commitments.add((s.teacher_id, s.day, s.period + p_offset))

        # 2. Count teacher daily teaching periods
        teacher_daily_classes: Dict[Tuple[str, str], int] = {}
        for (t_id, day, p) in teaching_commitments:
            teacher_daily_classes[(t_id, day)] = teacher_daily_classes.get((t_id, day), 0) + 1

        # 3. Track cumulative duty points per teacher
        teacher_duty_points: Dict[str, float] = {t_id: 0.0 for t_id in self.project.teachers}
        teacher_duty_counts: Dict[str, int] = {t_id: 0 for t_id in self.project.teachers}
        teacher_assigned_slots: Set[Tuple[str, str, int]] = set()  # (teacher_id, day, period)
        teacher_duty_days: Dict[str, Set[str]] = {t_id: set() for t_id in self.project.teachers}

        assignments: List[DutyAssignment] = []
        unfilled_slots = 0

        # Sort duty slots: heavier points weight & fewer available teachers first
        sorted_slots = list(self.project.duty_slots.values())
        sorted_slots.sort(key=lambda ds: (
            -self._get_duty_weight(ds.duty_type_id),
            ds.period  # Regular periods first, then recess/morning
        ))

        for slot in sorted_slots:
            weight = self._get_duty_weight(slot.duty_type_id)
            needed = slot.required_teachers

            # Find all eligible teachers for this slot
            candidates = []
            for t_id, teacher in self.project.teachers.items():
                # Hard Check 1: Is teacher teaching during this period?
                if slot.period > 0 and (t_id, slot.day, slot.period) in teaching_commitments:
                    continue

                # Hard Check 2: Already assigned another duty in this same slot?
                if (t_id, slot.day, slot.period) in teacher_assigned_slots:
                    continue

                # Hard Check 3: Is teacher unavailable on this day/period?
                if slot.period > 0 and not teacher.is_available(slot.day, slot.period):
                    continue

                # Soft scoring criteria:
                # 1. Current duty points (lowest points = highest priority)
                current_pts = teacher_duty_points.get(t_id, 0.0)
                # 2. Daily teaching load (teachers with fewer classes on this day preferred)
                classes_today = teacher_daily_classes.get((t_id, slot.day), 0)
                # 3. Has duty on this day already?
                has_duty_today = 1 if slot.day in teacher_duty_days[t_id] else 0

                fairness_score = (current_pts * 100.0) + (classes_today * 10.0) + (has_duty_today * 20.0)
                candidates.append((fairness_score, t_id, teacher.name))

            # Sort candidates by best fairness score (lowest)
            candidates.sort(key=lambda c: c[0])

            assigned_for_this_slot = 0
            for score, t_id, t_name in candidates[:needed]:
                assignment = DutyAssignment(
                    id=f"duty_assign_{uuid.uuid4().hex[:8]}",
                    duty_slot_id=slot.id,
                    teacher_id=t_id,
                    teacher_name=t_name,
                    day=slot.day,
                    period=slot.period,
                    duty_name=slot.duty_name,
                    location=slot.location,
                    time_label=slot.time_label
                )
                assignments.append(assignment)
                teacher_duty_points[t_id] = teacher_duty_points.get(t_id, 0.0) + weight
                teacher_duty_counts[t_id] = teacher_duty_counts.get(t_id, 0) + 1
                teacher_assigned_slots.add((t_id, slot.day, slot.period))
                teacher_duty_days[t_id].add(slot.day)
                assigned_for_this_slot += 1

            if assigned_for_this_slot < needed:
                unfilled_slots += (needed - assigned_for_this_slot)

        # Calculate fairness metrics
        counts = list(teacher_duty_counts.values())
        pts = list(teacher_duty_points.values())
        avg_duties = sum(counts) / len(counts) if counts else 0
        min_duties = min(counts) if counts else 0
        max_duties = max(counts) if counts else 0
        duty_range = max_duties - min_duties

        stats = {
            "total_assignments": len(assignments),
            "unfilled_slots": unfilled_slots,
            "average_duties_per_teacher": round(avg_duties, 2),
            "min_duties": min_duties,
            "max_duties": max_duties,
            "duty_spread_range": duty_range,
            "teacher_duty_counts": teacher_duty_counts,
            "teacher_duty_points": teacher_duty_points
        }

        msg = f"Duty roster generated! {len(assignments)} duties assigned across {len(self.project.teachers)} teachers. (Duty spread: {min_duties} to {max_duties})"
        if unfilled_slots > 0:
            msg += f" Note: {unfilled_slots} slot positions could not be filled due to teaching conflicts."

        return DutySolverResult(
            success=True,
            message=msg,
            assignments=assignments,
            stats=stats
        )

    def _get_duty_weight(self, duty_type_id: str) -> float:
        dt = self.project.duty_types.get(duty_type_id)
        return dt.points_weight if dt else 1.0

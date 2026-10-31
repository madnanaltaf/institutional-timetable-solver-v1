"""
Timetable Constraints & Scoring Metrics
Evaluates hard constraint feasibility and soft constraint quality penalties
(fatigue avoidance, subject dispersion, teacher load balancing, gap minimization).
"""
from typing import Dict, List, Set, Tuple, Optional, Any
from models.timetable_data import TimetableProject
from models.lesson import ScheduledSlot

class ConstraintWeights:
    """Configurable weights for soft constraints."""
    def __init__(
        self,
        subject_repetition_penalty: int = 120,   # Same subject multiple times in a day for section (fatigue)
        teacher_gap_penalty: int = 25,           # Idle period between teacher's classes
        teacher_consecutive_excess: int = 80,    # More than max consecutive periods
        teacher_daily_overload: int = 40,        # Exceeding preferred daily periods
        difficult_subject_afternoon: int = 20,   # Heavy cognitive subject in late periods
        section_gap_penalty: int = 200,          # Free period in middle of student's day
    ):
        self.subject_repetition_penalty = subject_repetition_penalty
        self.teacher_gap_penalty = teacher_gap_penalty
        self.teacher_consecutive_excess = teacher_consecutive_excess
        self.teacher_daily_overload = teacher_daily_overload
        self.difficult_subject_afternoon = difficult_subject_afternoon
        self.section_gap_penalty = section_gap_penalty


class SolutionEvaluator:
    """Evaluates the quality and penalty score of a timetable schedule."""
    def __init__(self, project: TimetableProject, weights: Optional[ConstraintWeights] = None):
        self.project = project
        self.weights = weights or ConstraintWeights()

    def evaluate_schedule(self, schedule: List[ScheduledSlot]) -> Dict[str, Any]:
        """
        Calculates total penalty score and detailed constraint breakdowns.
        Lower score = Higher quality timetable.
        """
        score = 0
        breakdown = {
            "subject_fatigue_penalties": 0,
            "teacher_gap_penalties": 0,
            "teacher_consecutive_penalties": 0,
            "teacher_overload_penalties": 0,
            "difficult_subject_afternoon_penalties": 0,
            "student_gap_penalties": 0,
            "total_score": 0
        }

        # 1. Section Daily Subject Distribution (Fatigue Avoidance)
        # Check if a section gets the same subject multiple times on the same day (unless it was a single block)
        sec_day_subs: Dict[Tuple[str, str], List[str]] = {}
        for s in schedule:
            key = (s.section_id, s.day)
            sec_day_subs.setdefault(key, []).append(s.subject_id)

        for (sec_id, day), sub_ids in sec_day_subs.items():
            counts: Dict[str, int] = {}
            for sid in sub_ids:
                counts[sid] = counts.get(sid, 0) + 1
            for sid, count in counts.items():
                if count > 1:
                    # Excess occurrences on the same day cause subject fatigue
                    penalty = (count - 1) * self.weights.subject_repetition_penalty
                    score += penalty
                    breakdown["subject_fatigue_penalties"] += penalty

        # 2. Teacher Gaps & Consecutive Periods
        # Combined all-sections sessions repeat the same teacher in several section
        # slots at the same time, so deduplicate periods per teacher/day.
        teacher_day_slots: Dict[Tuple[str, str], set] = {}
        for s in schedule:
            key = (s.teacher_id, s.day)
            bucket = teacher_day_slots.setdefault(key, set())
            for p in range(s.period, s.period + s.duration):
                bucket.add(p)

        for (t_id, day), periods in teacher_day_slots.items():
            periods = sorted(periods)
            teacher = self.project.teachers.get(t_id)
            max_consec = teacher.max_consecutive_periods if teacher else 3
            max_daily = teacher.max_periods_per_day if teacher else 5

            # Daily overload
            if len(periods) > max_daily:
                pen = (len(periods) - max_daily) * self.weights.teacher_daily_overload
                score += pen
                breakdown["teacher_overload_penalties"] += pen

            # Gaps between first and last period
            if len(periods) >= 2:
                span = periods[-1] - periods[0] + 1
                gaps = span - len(periods)
                if gaps > 0:
                    pen = gaps * self.weights.teacher_gap_penalty
                    score += pen
                    breakdown["teacher_gap_penalties"] += pen

            # Consecutive runs
            current_consec = 1
            for i in range(1, len(periods)):
                if periods[i] == periods[i - 1] + 1:
                    current_consec += 1
                    if current_consec > max_consec:
                        pen = self.weights.teacher_consecutive_excess
                        score += pen
                        breakdown["teacher_consecutive_penalties"] += pen
                else:
                    current_consec = 1

        # 3. Heavy/Difficult Subjects Late in Day
        break_period = self.project.institution.break_after_period
        for s in schedule:
            sub = self.project.subjects.get(s.subject_id)
            if sub and sub.is_difficult and s.period > break_period:
                pen = self.weights.difficult_subject_afternoon
                score += pen
                breakdown["difficult_subject_afternoon_penalties"] += pen

        # 4. Student Section Schedule Gaps
        sec_day_slots: Dict[Tuple[str, str], List[int]] = {}
        for s in schedule:
            key = (s.section_id, s.day)
            for p in range(s.period, s.period + s.duration):
                sec_day_slots.setdefault(key, []).append(p)

        for (sec_id, day), periods in sec_day_slots.items():
            periods.sort()
            if len(periods) >= 2:
                span = periods[-1] - periods[0] + 1
                gaps = span - len(periods)
                if gaps > 0:
                    pen = gaps * self.weights.section_gap_penalty
                    score += pen
                    breakdown["student_gap_penalties"] += pen

        breakdown["total_score"] = score
        return breakdown

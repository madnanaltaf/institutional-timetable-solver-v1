"""
Core Timetable Constraint Satisfaction Solver
Implements Backtracking with MRV (Minimum Remaining Values), Forward Checking,
Macro-Task Synchronization for Parallel Practicals, and Soft Constraint Optimization.
"""
import time
import random
import uuid
from typing import Dict, List, Set, Tuple, Optional, Callable, Any

from models.timetable_data import TimetableProject
from models.lesson import ScheduledSlot, LessonAllocation
from models.classroom import Classroom
from .constraints import ConstraintWeights, SolutionEvaluator
from .validator import ProjectValidator

class TaskItem:
    def __init__(
        self,
        task_id: str,
        lesson: LessonAllocation,
        duration: int,
        sync_group_id: str = "",
        combined_group_id: str = ""
    ):
        self.task_id = task_id
        self.lesson = lesson
        self.section_id = lesson.section_id
        self.subject_id = lesson.subject_id
        self.teacher_id = lesson.teacher_id
        self.preferred_room_id = lesson.room_id
        self.duration = duration
        self.sync_group_id = sync_group_id
        self.combined_group_id = combined_group_id

    def __repr__(self):
        return f"Task({self.task_id}: {self.section_id} {self.subject_id} T:{self.teacher_id} D:{self.duration})"


class MacroTask:
    """
    A collection of TaskItems that must be scheduled in the EXACT same (day, period).
    Used for aligned parallel practicals (e.g. Sec A CS Lab & Sec B Chem Lab).
    """
    def __init__(
        self,
        macro_id: str,
        tasks: List[TaskItem],
        duration: int,
        sync_group_id: str = "",
        combined_group_id: str = ""
    ):
        self.macro_id = macro_id
        self.tasks = tasks
        self.duration = duration
        self.sync_group_id = sync_group_id
        self.combined_group_id = combined_group_id
        self.is_combined = bool(combined_group_id)

    @property
    def sections(self) -> Set[str]:
        return {t.section_id for t in self.tasks}

    @property
    def teachers(self) -> Set[str]:
        return {t.teacher_id for t in self.tasks}

    def __repr__(self):
        return f"MacroTask({self.macro_id}, n_tasks={len(self.tasks)}, dur={self.duration})"


class SolverResult:
    def __init__(self, success: bool, message: str, schedule: List[ScheduledSlot], stats: Dict[str, Any]):
        self.success = success
        self.message = message
        self.schedule = schedule
        self.stats = stats


class TimetableSolver:
    def __init__(
        self,
        project: TimetableProject,
        weights: Optional[ConstraintWeights] = None,
        timeout_seconds: float = 25.0,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ):
        self.project = project
        self.weights = weights or ConstraintWeights()
        self.timeout_seconds = timeout_seconds
        self.progress_callback = progress_callback
        self.evaluator = SolutionEvaluator(project, self.weights)

        # Internal state
        self.macro_tasks: List[MacroTask] = []
        self.working_days = list(project.institution.working_days)
        self.periods_per_day = project.institution.periods_per_day
        self.break_after_period = project.institution.break_after_period

        # Reservation sets: (day, period, entity_id)
        self.section_occupancy: Set[Tuple[str, int, str]] = set()
        self.teacher_occupancy: Set[Tuple[str, int, str]] = set()
        self.room_occupancy: Set[Tuple[str, int, str]] = set()

        # Subject per section per day tracking for fatigue avoidance
        self.section_day_subjects: Dict[Tuple[str, str], List[str]] = {}

        # Preserve any user-locked slots
        self.locked_slots: List[ScheduledSlot] = [s for s in self.project.schedule if getattr(s, 'is_locked', False)]

        # Assignments: macro_id -> (day, start_period, task_rooms: Dict[task_id, room_id])
        self.assignments: Dict[str, Tuple[str, int, Dict[str, str]]] = {}

        self.start_time = 0.0
        self.nodes_explored = 0
        self.backtracks = 0
        self.best_solution: Optional[List[ScheduledSlot]] = None
        self.best_score = float("inf")

    def solve(self) -> SolverResult:
        """Main entry point to execute timetable generation."""
        self.start_time = time.time()
        self.nodes_explored = 0
        self.backtracks = 0

        # 1. Pre-validation
        validator = ProjectValidator(self.project)
        issues = validator.validate()
        errors = [i for i in issues if i.severity == "ERROR"]
        if errors:
            err_msg = "\n".join([f"• {e.title}: {e.description}" for e in errors])
            return SolverResult(
                success=False,
                message=f"Validation failed with {len(errors)} error(s):\n{err_msg}",
                schedule=[],
                stats={"errors": [e.to_dict() for e in errors]}
            )

        # 2. Decompose lessons into MacroTasks
        self._prepare_macro_tasks()

        if not self.macro_tasks:
            return SolverResult(
                success=True,
                message="No lessons to schedule. Generated empty timetable.",
                schedule=[],
                stats={"total_lessons": 0}
            )

        # 3. Solve with iterative randomized restarts if needed
        max_restarts = 5
        solution_found = False

        for restart in range(max_restarts):
            if time.time() - self.start_time > self.timeout_seconds:
                break

            self._reset_state()
            if restart > 0:
                # Add slight random jitter to MacroTask order for variety
                random.shuffle(self.macro_tasks)

            if self.progress_callback:
                self.progress_callback(
                    0, len(self.macro_tasks),
                    f"Solving (Attempt {restart + 1}/{max_restarts})..."
                )

            success = self._backtrack(0)
            if success:
                solution_found = True
                break

        elapsed = time.time() - self.start_time

        if solution_found:
            scheduled_slots = self._build_scheduled_slots()
            evaluation = self.evaluator.evaluate_schedule(scheduled_slots)

            stats = {
                "elapsed_seconds": round(elapsed, 2),
                "nodes_explored": self.nodes_explored,
                "backtracks": self.backtracks,
                "total_slots_scheduled": len(scheduled_slots),
                "quality_score": evaluation["total_score"],
                "penalties_breakdown": evaluation
            }

            return SolverResult(
                success=True,
                message=f"Timetable generated successfully in {elapsed:.2f}s! ({len(scheduled_slots)} slots, score: {evaluation['total_score']})",
                schedule=scheduled_slots,
                stats=stats
            )
        else:
            return SolverResult(
                success=False,
                message=f"Could not find a conflict-free solution within {elapsed:.1f}s. "
                        f"Try relaxing constraints, adding teachers, or balancing lab allocations.",
                schedule=[],
                stats={
                    "elapsed_seconds": round(elapsed, 2),
                    "nodes_explored": self.nodes_explored,
                    "backtracks": self.backtracks
                }
            )

    def _prepare_macro_tasks(self):
        """Builds MacroTasks, grouping synchronized practicals and combined
        all-sections sessions that must share one exact time slot."""
        self.macro_tasks = []
        sync_groups: Dict[str, List[TaskItem]] = {}
        combined_groups: Dict[str, List[TaskItem]] = {}
        standalone_tasks: List[TaskItem] = []

        # Deduct periods already fulfilled by user-locked slots
        locked_periods_by_lesson: Dict[str, int] = {}
        for s in self.locked_slots:
            locked_periods_by_lesson[s.lesson_id] = locked_periods_by_lesson.get(s.lesson_id, 0) + s.duration

        for lesson_id, lesson in self.project.lessons.items():
            already_locked = locked_periods_by_lesson.get(lesson_id, 0)
            total_periods = max(0, lesson.periods_per_week - already_locked)
            if total_periods <= 0:
                continue

            block_size = max(1, lesson.block_size)
            num_blocks = total_periods // block_size
            remainder = total_periods % block_size

            # Create blocks
            for b in range(num_blocks):
                item = TaskItem(
                    task_id=f"T_{lesson_id}_{b}",
                    lesson=lesson,
                    duration=block_size,
                    sync_group_id=lesson.sync_group_id,
                    combined_group_id=lesson.combined_group_id
                )
                if lesson.combined_group_id:
                    combined_groups.setdefault(lesson.combined_group_id, []).append(item)
                elif lesson.sync_group_id:
                    sync_groups.setdefault(lesson.sync_group_id, []).append(item)
                else:
                    standalone_tasks.append(item)

            # Remainder single periods stay aligned with their group
            for r in range(remainder):
                item = TaskItem(
                    task_id=f"T_{lesson_id}_rem_{r}",
                    lesson=lesson,
                    duration=1,
                    sync_group_id=lesson.sync_group_id,
                    combined_group_id=lesson.combined_group_id
                )
                if lesson.combined_group_id:
                    combined_groups.setdefault(lesson.combined_group_id, []).append(item)
                elif lesson.sync_group_id:
                    sync_groups.setdefault(lesson.sync_group_id, []).append(item)
                else:
                    standalone_tasks.append(item)

        macro_idx = 1

        def add_grouped_macros(groups: Dict[str, List[TaskItem]], is_combined: bool):
            nonlocal macro_idx
            for group_id, items in groups.items():
                # Items in a group might belong to different pairs/blocks.
                # Group items by section first, then pair instance by instance.
                sec_to_items: Dict[str, List[TaskItem]] = {}
                for it in items:
                    sec_to_items.setdefault(it.section_id, []).append(it)

                max_instances = max(len(lst) for lst in sec_to_items.values())
                for inst in range(max_instances):
                    coupled_tasks = [
                        sec_items[inst]
                        for sec_items in sec_to_items.values()
                        if inst < len(sec_items)
                    ]
                    duration = max(t.duration for t in coupled_tasks)
                    self.macro_tasks.append(MacroTask(
                        macro_id=f"MACRO_{'COMB' if is_combined else 'SYNC'}_{macro_idx}",
                        tasks=coupled_tasks,
                        duration=duration,
                        sync_group_id="" if is_combined else group_id,
                        combined_group_id=group_id if is_combined else ""
                    ))
                    macro_idx += 1

        add_grouped_macros(combined_groups, True)
        add_grouped_macros(sync_groups, False)

        # Add standalone tasks as single-task macros
        for task in standalone_tasks:
            macro = MacroTask(
                macro_id=f"MACRO_STD_{macro_idx}",
                tasks=[task],
                duration=task.duration
            )
            self.macro_tasks.append(macro)
            macro_idx += 1

        # Heuristic sort: combined sessions first (hardest), then larger groups,
        # then longer duration, then higher priority
        self.macro_tasks.sort(
            key=lambda m: (
                0 if m.is_combined else 1,
                -len(m.tasks),
                -m.duration,
                -max(t.lesson.priority for t in m.tasks)
            )
        )

    def _reset_state(self):
        self.section_occupancy.clear()
        self.teacher_occupancy.clear()
        self.room_occupancy.clear()
        self.section_day_subjects.clear()
        self.assignments.clear()

        # Pre-populate occupancy from user-locked slots
        for s in self.locked_slots:
            for d_p in range(s.period, s.period + s.duration):
                self.section_occupancy.add((s.day, d_p, s.section_id))
                self.teacher_occupancy.add((s.day, d_p, s.teacher_id))
                if s.room_id:
                    self.room_occupancy.add((s.day, d_p, s.room_id))
            self.section_day_subjects.setdefault((s.day, s.section_id), []).append(s.subject_id)

    def _backtrack(self, index: int) -> bool:
        """Recursive backtracking with MRV and constraint propagation."""
        self.nodes_explored += 1

        if time.time() - self.start_time > self.timeout_seconds:
            return False

        if index >= len(self.macro_tasks):
            return True  # All scheduled!

        # Select next macro-task using MRV (Minimum Remaining Values)
        best_macro_idx = index
        best_candidates = None
        min_candidate_count = float("inf")

        # Inspect unassigned macros to pick the most constrained
        for i in range(index, min(index + 8, len(self.macro_tasks))):
            m = self.macro_tasks[i]
            candidates = self._find_valid_slots_with_penalties(m)
            if len(candidates) < min_candidate_count:
                min_candidate_count = len(candidates)
                best_macro_idx = i
                best_candidates = candidates
                if min_candidate_count == 0:
                    break

        if min_candidate_count == 0:
            self.backtracks += 1
            return False  # Dead end

        # Swap best into current position
        self.macro_tasks[index], self.macro_tasks[best_macro_idx] = self.macro_tasks[best_macro_idx], self.macro_tasks[index]
        macro = self.macro_tasks[index]

        if best_candidates is None:
            best_candidates = self._find_valid_slots_with_penalties(macro)

        # Sort candidate slots by soft penalty score (lowest penalty first)
        best_candidates.sort(key=lambda c: c[0])

        if self.progress_callback and (self.nodes_explored % 50 == 0):
            assigned = index
            total = len(self.macro_tasks)
            self.progress_callback(
                assigned, total,
                f"Scheduling {assigned}/{total} lessons ({self.nodes_explored} steps)..."
            )

        for penalty, day, period, room_assignments in best_candidates:
            # Apply assignment
            self._apply_assignment(macro, day, period, room_assignments)

            # Recurse
            if self._backtrack(index + 1):
                return True

            # Undo assignment
            self._undo_assignment(macro, day, period, room_assignments)
            self.backtracks += 1

        return False

    def _find_valid_slots_with_penalties(
        self, macro: MacroTask
    ) -> List[Tuple[int, str, int, Dict[str, str]]]:
        """
        Finds all (day, period) slots that satisfy hard constraints,
        and computes their soft constraint penalty.
        """
        valid_options = []
        is_incharge_macro = any(
            t.section_id in self.project.sections and self.project.sections[t.section_id].class_teacher_id == t.teacher_id
            for t in macro.tasks
        )
        teacher_incharge_sec = {sec.class_teacher_id: sec.id for sec in self.project.sections.values() if sec.class_teacher_id}

        for day in self.working_days:
            day_periods = self.project.institution.get_periods_for_day(day)
            max_p = day_periods - macro.duration + 1

            if is_incharge_macro:
                period_order = list(range(1, max_p + 1))
            else:
                period_order = list(range(2, max_p + 1)) + ([1] if max_p >= 1 else [])

            for p in period_order:
                # Class incharge must take first lecture in their class:
                # Do not schedule incharge teachers in Period 1 for classes other than their own incharge class
                if p == 1 and not is_incharge_macro:
                    has_incharge_teacher = any(t.teacher_id in teacher_incharge_sec for t in macro.tasks)
                    if has_incharge_teacher:
                        continue

                # 1. Recess break collision check for multi-period blocks
                if macro.duration > 1:
                    # If break is after period B, cannot start at <= B and end at > B
                    if p <= self.break_after_period < p + macro.duration:
                        continue

                # Combined sessions can share one venue (e.g. auditorium) when all
                # their allocations point at the same room.
                shared_room_id = ""
                if macro.is_combined:
                    preferred = {t.preferred_room_id for t in macro.tasks}
                    if len(preferred) == 1 and next(iter(preferred)):
                        shared_room_id = next(iter(preferred))

                # 2. Check hard constraints for all tasks in the macro
                hard_ok = True
                task_rooms: Dict[str, str] = {}

                if shared_room_id:
                    if shared_room_id not in self.project.classrooms:
                        continue
                    if any(
                        (day, d_p, shared_room_id) in self.room_occupancy
                        for d_p in range(p, p + macro.duration)
                    ):
                        continue

                for task in macro.tasks:
                    # Section free?
                    for d_p in range(p, p + macro.duration):
                        if (day, d_p, task.section_id) in self.section_occupancy:
                            hard_ok = False
                            break
                    if not hard_ok:
                        break

                    # Teacher free & available?
                    # Combined sessions intentionally put the same teacher in every
                    # section at this time, so the shared teacher is checked once.
                    teacher = self.project.teachers.get(task.teacher_id)
                    if teacher:
                        for d_p in range(p, p + macro.duration):
                            if (day, d_p, task.teacher_id) in self.teacher_occupancy:
                                hard_ok = False
                                break
                            if not teacher.is_available(day, d_p):
                                hard_ok = False
                                break
                    if not hard_ok:
                        break

                    if shared_room_id:
                        task_rooms[task.task_id] = shared_room_id
                    else:
                        assigned_room = self._find_available_room(task, day, p, macro.duration, task_rooms)
                        if not assigned_room:
                            hard_ok = False
                            break
                        task_rooms[task.task_id] = assigned_room

                if not hard_ok:
                    continue

                # Compute soft penalty
                penalty = self._calculate_placement_penalty(macro, day, p)
                valid_options.append((penalty, day, p, task_rooms))

        return valid_options

    def _find_available_room(
        self,
        task: TaskItem,
        day: str,
        period: int,
        duration: int,
        already_allocated_in_step: Dict[str, str]
    ) -> Optional[str]:
        """Finds a conflict-free room matching the subject/task requirements."""
        # Preferred room specified?
        if task.preferred_room_id and task.preferred_room_id in self.project.classrooms:
            room_id = task.preferred_room_id
            if room_id in already_allocated_in_step.values():
                return None
            for d_p in range(period, period + duration):
                if (day, d_p, room_id) in self.room_occupancy:
                    return None
            return room_id

        # Section home room?
        sec = self.project.sections.get(task.section_id)
        sub = self.project.subjects.get(task.subject_id)

        # If subject requires lab, must find a room of required type
        req_type = sub.default_room_type if sub else "General Classroom"

        # Candidate rooms
        matching_rooms = [
            r for r in self.project.classrooms.values()
            if r.room_type == req_type or (req_type == "General Classroom" and "Classroom" in r.room_type)
        ]

        # Prioritize home room if suitable
        if sec and sec.home_room_id:
            home = self.project.classrooms.get(sec.home_room_id)
            if home and home in matching_rooms:
                matching_rooms.remove(home)
                matching_rooms.insert(0, home)

        for room in matching_rooms:
            if room.id in already_allocated_in_step.values():
                continue
            free = True
            for d_p in range(period, period + duration):
                if (day, d_p, room.id) in self.room_occupancy:
                    free = False
                    break
            if free:
                return room.id

        return None

    def _calculate_placement_penalty(self, macro: MacroTask, day: str, period: int) -> int:
        """Calculates soft constraint penalty for placing macro-task at (day, period)."""
        penalty = 0

        for task in macro.tasks:
            # 1. Fatigue: Avoid same subject on same day for section
            sec_subs = self.section_day_subjects.get((task.section_id, day), [])
            if task.subject_id in sec_subs:
                penalty += self.weights.subject_repetition_penalty

            # 2. Cognitive fatigue: Difficult subjects afternoon penalty
            sub = self.project.subjects.get(task.subject_id)
            if sub and sub.is_difficult and period > self.break_after_period:
                penalty += self.weights.difficult_subject_afternoon

            # 3. Teacher load balancing for the day
            day_max_p = self.project.institution.get_periods_for_day(day)
            teacher_daily_count = sum(
                1 for p in range(1, day_max_p + 1)
                if (day, p, task.teacher_id) in self.teacher_occupancy
            )
            teacher = self.project.teachers.get(task.teacher_id)
            max_d = teacher.max_periods_per_day if teacher else 5
            if teacher_daily_count + macro.duration > max_d:
                penalty += self.weights.teacher_daily_overload

            # 4. Teacher gap penalty
            prev_taught = ((day, period - 1, task.teacher_id) in self.teacher_occupancy) if period > 1 else False
            next_taught = ((day, period + macro.duration, task.teacher_id) in self.teacher_occupancy) if period + macro.duration <= day_max_p else False
            
            gap_before = (period > 2 and (day, period - 2, task.teacher_id) in self.teacher_occupancy and not prev_taught)
            gap_after = (period + macro.duration + 1 <= day_max_p and (day, period + macro.duration + 1, task.teacher_id) in self.teacher_occupancy and not next_taught)
            if gap_before or gap_after:
                penalty += self.weights.teacher_gap_penalty

        return penalty

    def _apply_assignment(self, macro: MacroTask, day: str, period: int, room_assignments: Dict[str, str]):
        self.assignments[macro.macro_id] = (day, period, room_assignments)

        for task in macro.tasks:
            room_id = room_assignments.get(task.task_id, "")
            for d_p in range(period, period + macro.duration):
                self.section_occupancy.add((day, d_p, task.section_id))
                self.teacher_occupancy.add((day, d_p, task.teacher_id))
                if room_id:
                    self.room_occupancy.add((day, d_p, room_id))

            self.section_day_subjects.setdefault((task.section_id, day), []).append(task.subject_id)

    def _undo_assignment(self, macro: MacroTask, day: str, period: int, room_assignments: Dict[str, str]):
        if macro.macro_id in self.assignments:
            del self.assignments[macro.macro_id]

        for task in macro.tasks:
            room_id = room_assignments.get(task.task_id, "")
            for d_p in range(period, period + macro.duration):
                self.section_occupancy.discard((day, d_p, task.section_id))
                self.teacher_occupancy.discard((day, d_p, task.teacher_id))
                if room_id:
                    self.room_occupancy.discard((day, d_p, room_id))

            subs = self.section_day_subjects.get((task.section_id, day), [])
            if task.subject_id in subs:
                subs.remove(task.subject_id)

    def _build_scheduled_slots(self) -> List[ScheduledSlot]:
        """Converts internal assignments into list of ScheduledSlot objects, including preserved locked slots."""
        slots = list(self.locked_slots)
        for macro in self.macro_tasks:
            if macro.macro_id not in self.assignments:
                continue
            day, period, room_map = self.assignments[macro.macro_id]
            for task in macro.tasks:
                room_id = room_map.get(task.task_id, task.preferred_room_id)
                slot = ScheduledSlot(
                    id=f"slot_{uuid.uuid4().hex[:8]}",
                    lesson_id=task.lesson.id,
                    section_id=task.section_id,
                    subject_id=task.subject_id,
                    teacher_id=task.teacher_id,
                    room_id=room_id,
                    day=day,
                    period=period,
                    duration=macro.duration,
                    sync_group_id=macro.sync_group_id,
                    combined_group_id=macro.combined_group_id,
                    all_sections=macro.is_combined
                )
                slots.append(slot)
        return slots

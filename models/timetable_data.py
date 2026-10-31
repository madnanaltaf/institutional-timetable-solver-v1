"""
Central Timetable Project Model
Encapsulates all institutional data, schedule slots, duty rosters, and project persistence.
"""
import json
import uuid
import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any

from .institution import InstitutionSettings
from .subject import Subject, PALETTE_COLORS, ROOM_TYPES
from .teacher import Teacher
from .classroom import Classroom
from .section import GradeClass, Section
from .lesson import LessonAllocation, ScheduledSlot
from .duty import DutyType, DutySlot, DutyAssignment

@dataclass
class TimetableProject:
    institution: InstitutionSettings = field(default_factory=InstitutionSettings)
    classes: Dict[str, GradeClass] = field(default_factory=dict)
    sections: Dict[str, Section] = field(default_factory=dict)
    subjects: Dict[str, Subject] = field(default_factory=dict)
    teachers: Dict[str, Teacher] = field(default_factory=dict)
    classrooms: Dict[str, Classroom] = field(default_factory=dict)
    lessons: Dict[str, LessonAllocation] = field(default_factory=dict)
    duty_types: Dict[str, DutyType] = field(default_factory=dict)
    duty_slots: Dict[str, DutySlot] = field(default_factory=dict)
    duty_assignments: List[DutyAssignment] = field(default_factory=list)
    schedule: List[ScheduledSlot] = field(default_factory=list)
    is_generated: bool = False
    last_generated_time: str = ""
    solve_stats: Dict[str, Any] = field(default_factory=dict)

    # ------------------ Query Helpers ------------------ #
    def get_section_slots(self, section_id: str) -> List[ScheduledSlot]:
        return [s for s in self.schedule if s.section_id == section_id]

    def get_teacher_slots(self, teacher_id: str) -> List[ScheduledSlot]:
        return [s for s in self.schedule if s.teacher_id == teacher_id]

    def get_room_slots(self, room_id: str) -> List[ScheduledSlot]:
        return [s for s in self.schedule if s.room_id == room_id]

    def get_subject_slots(self, subject_id: str) -> List[ScheduledSlot]:
        return [s for s in self.schedule if s.subject_id == subject_id]

    def get_slot_at(self, day: str, period: int, section_id: str) -> Optional[ScheduledSlot]:
        for s in self.schedule:
            if s.day == day and s.section_id == section_id:
                if s.period <= period < s.period + s.duration:
                    return s
        return None

    def get_teacher_slot_at(self, day: str, period: int, teacher_id: str) -> Optional[ScheduledSlot]:
        for s in self.schedule:
            if s.day == day and s.teacher_id == teacher_id:
                if s.period <= period < s.period + s.duration:
                    return s
        return None

    def get_room_slot_at(self, day: str, period: int, room_id: str) -> Optional[ScheduledSlot]:
        for s in self.schedule:
            if s.day == day and s.room_id == room_id:
                if s.period <= period < s.period + s.duration:
                    return s
        return None

    def get_teacher_duties(self, teacher_id: str) -> List[DutyAssignment]:
        return [d for d in self.duty_assignments if d.teacher_id == teacher_id]

    def get_teacher_duty_at(self, day: str, period: int, teacher_id: str) -> Optional[DutyAssignment]:
        for d in self.duty_assignments:
            if d.teacher_id == teacher_id and d.day == day and d.period == period:
                return d
        return None

    def get_class_sections(self, class_id: str) -> List[Section]:
        return [sec for sec in self.sections.values() if sec.class_id == class_id]

    def get_combined_group_lessons(self, group_id: str) -> List[LessonAllocation]:
        """Returns the per-section allocations that form one combined session."""
        return [l for l in self.lessons.values() if group_id and l.combined_group_id == group_id]

    def get_alignment_group(self, slot: ScheduledSlot) -> List[ScheduledSlot]:
        """Returns every slot that must stay at the same time as this one
        (its synchronized/combined peers in the same day and period)."""
        if not slot.sync_group_id and not slot.combined_group_id:
            return [slot]
        return [
            s for s in self.schedule
            if s.day == slot.day and s.period == slot.period and (
                (slot.combined_group_id and s.combined_group_id == slot.combined_group_id)
                or (slot.sync_group_id and s.sync_group_id == slot.sync_group_id)
            )
        ]

    def get_teachers_for_subject(self, subject_id: str) -> List[Teacher]:
        """Returns teachers who specialize/are qualified in this subject."""
        return [t for t in self.teachers.values() if subject_id in t.qualified_subjects]

    def get_teacher_allocated_periods(self, teacher_id: str) -> int:
        """Returns total weekly periods currently allocated to this teacher across all lessons.

        A combined all-sections session is taught once, so it is counted once even though
        it has one allocation row per section.
        """
        total = 0
        counted_groups = set()
        for l in self.lessons.values():
            if l.teacher_id != teacher_id:
                continue
            if l.combined_group_id:
                if l.combined_group_id in counted_groups:
                    continue
                counted_groups.add(l.combined_group_id)
            total += l.periods_per_week
        return total

    def get_section_allocated_periods(self, section_id: str) -> int:
        """Returns total weekly periods currently allocated to this section across all lessons."""
        return sum(l.periods_per_week for l in self.lessons.values() if l.section_id == section_id)

    def get_section_lessons(self, section_id: str) -> List[LessonAllocation]:
        """Returns all lesson allocations for a specific class section."""
        return [l for l in self.lessons.values() if l.section_id == section_id]

    def get_teacher_lessons(self, teacher_id: str) -> List[LessonAllocation]:
        """Returns all lesson allocations taught by a teacher."""
        return [l for l in self.lessons.values() if l.teacher_id == teacher_id]

    def clear_schedule(self):
        self.schedule.clear()
        self.duty_assignments.clear()
        self.is_generated = False
        self.last_generated_time = ""
        self.solve_stats = {}

    # ------------------ Serialization ------------------ #
    def to_dict(self) -> Dict[str, Any]:
        return {
            "institution": self.institution.to_dict(),
            "classes": {k: v.to_dict() for k, v in self.classes.items()},
            "sections": {k: v.to_dict() for k, v in self.sections.items()},
            "subjects": {k: v.to_dict() for k, v in self.subjects.items()},
            "teachers": {k: v.to_dict() for k, v in self.teachers.items()},
            "classrooms": {k: v.to_dict() for k, v in self.classrooms.items()},
            "lessons": {k: v.to_dict() for k, v in self.lessons.items()},
            "duty_types": {k: v.to_dict() for k, v in self.duty_types.items()},
            "duty_slots": {k: v.to_dict() for k, v in self.duty_slots.items()},
            "duty_assignments": [d.to_dict() for d in self.duty_assignments],
            "schedule": [s.to_dict() for s in self.schedule],
            "is_generated": self.is_generated,
            "last_generated_time": self.last_generated_time,
            "solve_stats": self.solve_stats
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TimetableProject":
        proj = cls()
        if "institution" in data:
            proj.institution = InstitutionSettings.from_dict(data["institution"])
        if "classes" in data:
            proj.classes = {k: GradeClass.from_dict(v) for k, v in data["classes"].items()}
        if "sections" in data:
            proj.sections = {k: Section.from_dict(v) for k, v in data["sections"].items()}
        if "subjects" in data:
            proj.subjects = {k: Subject.from_dict(v) for k, v in data["subjects"].items()}
        if "teachers" in data:
            proj.teachers = {k: Teacher.from_dict(v) for k, v in data["teachers"].items()}
        if "classrooms" in data:
            proj.classrooms = {k: Classroom.from_dict(v) for k, v in data["classrooms"].items()}
        if "lessons" in data:
            proj.lessons = {k: LessonAllocation.from_dict(v) for k, v in data["lessons"].items()}
        if "duty_types" in data:
            proj.duty_types = {k: DutyType.from_dict(v) for k, v in data["duty_types"].items()}
        if "duty_slots" in data:
            proj.duty_slots = {k: DutySlot.from_dict(v) for k, v in data["duty_slots"].items()}
        if "duty_assignments" in data:
            proj.duty_assignments = [DutyAssignment.from_dict(d) for d in data["duty_assignments"]]
        if "schedule" in data:
            proj.schedule = [ScheduledSlot.from_dict(s) for s in data["schedule"]]
        proj.is_generated = data.get("is_generated", False)
        proj.last_generated_time = data.get("last_generated_time", "")
        proj.solve_stats = data.get("solve_stats", {})
        return proj

    def save_to_file(self, filepath: str):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, filepath: str) -> "TimetableProject":
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)

    # ------------------ Sample College Factory ------------------ #
    @classmethod
    def create_sample_institution(cls) -> "TimetableProject":
        """
        Creates a realistic, comprehensive school/college dataset with:
        - 2 Grade Classes (Grade 10 & Grade 11), each with 2 Sections (A & B)
        - Aligned Synchronized Practicals:
          * Sec A CS Lab synchronized with Sec B Chem Lab (simultaneous 2-period lab block)
          * Sec A Chem Lab synchronized with Sec B CS Lab
        - Diverse subjects (Theory & Labs) with color coding
        - 10+ Qualified Teachers with realistic availability
        - Classrooms and Specialized Labs
        - Duty Slots (Morning Assembly, Recess, Exam Invigilation)
        """
        proj = cls()
        proj.institution = InstitutionSettings(
            name="Cambridge Science & Technology Academy",
            academic_year="2026 - 2027",
            term="Semester 1 (Academic Year)",
            motto="Innovate, Explore, Excel",
            working_days=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
            periods_per_day=7,
            break_after_period=4,
            period_duration_mins=45,
            break_duration_mins=30,
            start_hour=8,
            start_min=30
        )
        proj.institution.generate_default_period_times()

        # Classrooms & Specialized Labs
        rooms = [
            Classroom(id="r_101", name="Room 101", room_type="General Classroom", capacity=40, building="Wing A"),
            Classroom(id="r_102", name="Room 102", room_type="General Classroom", capacity=40, building="Wing A"),
            Classroom(id="r_201", name="Room 201", room_type="General Classroom", capacity=40, building="Wing B"),
            Classroom(id="r_202", name="Room 202", room_type="General Classroom", capacity=40, building="Wing B"),
            Classroom(id="lab_cs", name="Computer Science Lab", room_type="Computer Lab", capacity=36, building="Tech Centre"),
            Classroom(id="lab_chem", name="Chemistry Research Lab", room_type="Chemistry Lab", capacity=36, building="Science Complex"),
            Classroom(id="lab_phy", name="Physics Lab", room_type="Physics Lab", capacity=36, building="Science Complex"),
            Classroom(id="ground", name="Main Sports Ground", room_type="Sports Ground / Gym", capacity=80, building="Outdoor Arena")
        ]
        for r in rooms:
            proj.classrooms[r.id] = r

        # Classes
        c10 = GradeClass(id="c_10", name="Grade 10")
        c11 = GradeClass(id="c_11", name="Grade 11")
        proj.classes[c10.id] = c10
        proj.classes[c11.id] = c11

        # Sections
        sec_10a = Section(id="s_10a", class_id="c_10", class_name="Grade 10", name="Section A", student_count=32, home_room_id="r_101")
        sec_10b = Section(id="s_10b", class_id="c_10", class_name="Grade 10", name="Section B", student_count=30, home_room_id="r_102")
        sec_11a = Section(id="s_11a", class_id="c_11", class_name="Grade 11", name="Section A", student_count=28, home_room_id="r_201")
        sec_11b = Section(id="s_11b", class_id="c_11", class_name="Grade 11", name="Section B", student_count=29, home_room_id="r_202")
        for s in [sec_10a, sec_10b, sec_11a, sec_11b]:
            proj.sections[s.id] = s

        # Subjects
        subs = [
            Subject(id="sub_math", code="MATH", name="Mathematics", subject_type="Theory", color="#2563EB", is_difficult=True),
            Subject(id="sub_phy", code="PHY", name="Physics (Theory)", subject_type="Theory", color="#7C3AED", is_difficult=True),
            Subject(id="sub_phy_lab", code="PHY-LAB", name="Physics Lab Practical", subject_type="Practical Lab", color="#6D28D9", requires_lab=True, default_room_type="Physics Lab", allowed_double_period=True),
            Subject(id="sub_chem", code="CHEM", name="Chemistry (Theory)", subject_type="Theory", color="#059669", is_difficult=True),
            Subject(id="sub_chem_lab", code="CHEM-LAB", name="Chemistry Lab Practical", subject_type="Practical Lab", color="#047857", requires_lab=True, default_room_type="Chemistry Lab", allowed_double_period=True),
            Subject(id="sub_cs", code="CS", name="Computer Science", subject_type="Theory", color="#0284C7"),
            Subject(id="sub_cs_lab", code="CS-LAB", name="Computer Science Lab", subject_type="Practical Lab", color="#0369A1", requires_lab=True, default_room_type="Computer Lab", allowed_double_period=True),
            Subject(id="sub_eng", code="ENG", name="English Literature", subject_type="Theory", color="#D97706"),
            Subject(id="sub_bio", code="BIO", name="Biology", subject_type="Theory", color="#16A34A"),
            Subject(id="sub_hist", code="HIST", name="World History", subject_type="Theory", color="#DC2626"),
            Subject(id="sub_pe", code="PE", name="Physical Education", subject_type="PE", color="#EA580C", default_room_type="Sports Ground / Gym")
        ]
        for sub in subs:
            proj.subjects[sub.id] = sub

        # Teachers
        teachers = [
            Teacher(id="t_turing", name="Dr. Alan Turing", code="AT", email="turing@academy.edu", qualified_subjects=["sub_math", "sub_cs", "sub_cs_lab"], max_periods_per_day=5, color="#1D4ED8"),
            Teacher(id="t_curie", name="Prof. Marie Curie", code="MC", email="curie@academy.edu", qualified_subjects=["sub_chem", "sub_chem_lab", "sub_phy"], max_periods_per_day=5, color="#047857"),
            Teacher(id="t_newton", name="Sir Isaac Newton", code="IN", email="newton@academy.edu", qualified_subjects=["sub_phy", "sub_phy_lab", "sub_math"], max_periods_per_day=5, color="#6D28D9"),
            Teacher(id="t_lovelace", name="Ada Lovelace", code="AL", email="lovelace@academy.edu", qualified_subjects=["sub_cs", "sub_cs_lab", "sub_math"], max_periods_per_day=5, color="#0284C7"),
            Teacher(id="t_darwin", name="Charles Darwin", code="CD", email="darwin@academy.edu", qualified_subjects=["sub_bio", "sub_chem"], max_periods_per_day=5, color="#15803D"),
            Teacher(id="t_orwell", name="George Orwell", code="GO", email="orwell@academy.edu", qualified_subjects=["sub_eng", "sub_hist"], max_periods_per_day=5, color="#B45309"),
            Teacher(id="t_franklin", name="Rosalind Franklin", code="RF", email="franklin@academy.edu", qualified_subjects=["sub_chem", "sub_chem_lab", "sub_bio"], max_periods_per_day=5, color="#0F766E"),
            Teacher(id="t_einstein", name="Albert Einstein", code="AE", email="einstein@academy.edu", qualified_subjects=["sub_phy", "sub_math"], max_periods_per_day=4, color="#4338CA"),
            Teacher(id="t_shakespeare", name="William Shakespeare", code="WS", email="shakespeare@academy.edu", qualified_subjects=["sub_eng"], max_periods_per_day=5, color="#C2410C"),
            Teacher(id="t_bolt", name="Usain Bolt", code="UB", email="bolt@academy.edu", qualified_subjects=["sub_pe"], max_periods_per_day=4, color="#C05621")
        ]
        # Some realistic teacher unavailabilities (e.g. Einstein not available Friday late)
        teachers[7].add_unavailable_slot("Friday", 6)
        teachers[7].add_unavailable_slot("Friday", 7)
        for t in teachers:
            proj.teachers[t.id] = t

        # Curriculum Allocations & Synchronized Science Practicals!
        # Notice:
        # Grade 10:
        # Sec A & Sec B:
        # Synchronized Pair 1: Sec A has CS-LAB (2 periods) while Sec B has CHEM-LAB (2 periods)
        # Synchronized Pair 2: Sec A has CHEM-LAB (2 periods) while Sec B has CS-LAB (2 periods)
        allocations = [
            # Grade 10 - Section A
            LessonAllocation(id="L_10A_MATH", section_id="s_10a", subject_id="sub_math", teacher_id="t_turing", room_id="r_101", periods_per_week=5, block_size=1),
            LessonAllocation(id="L_10A_ENG", section_id="s_10a", subject_id="sub_eng", teacher_id="t_shakespeare", room_id="r_101", periods_per_week=4, block_size=1),
            LessonAllocation(id="L_10A_PHY", section_id="s_10a", subject_id="sub_phy", teacher_id="t_einstein", room_id="r_101", periods_per_week=4, block_size=1),
            LessonAllocation(id="L_10A_CHEM", section_id="s_10a", subject_id="sub_chem", teacher_id="t_curie", room_id="r_101", periods_per_week=3, block_size=1),
            LessonAllocation(id="L_10A_BIO", section_id="s_10a", subject_id="sub_bio", teacher_id="t_darwin", room_id="r_101", periods_per_week=3, block_size=1),
            LessonAllocation(id="L_10A_HIST", section_id="s_10a", subject_id="sub_hist", teacher_id="t_orwell", room_id="r_101", periods_per_week=3, block_size=1),
            LessonAllocation(id="L_10A_CS_TH", section_id="s_10a", subject_id="sub_cs", teacher_id="t_lovelace", room_id="r_101", periods_per_week=2, block_size=1),
            LessonAllocation(id="L_10A_PE", section_id="s_10a", subject_id="sub_pe", teacher_id="t_bolt", room_id="ground", periods_per_week=2, block_size=1),
            # Aligned Practicals for Grade 10:
            LessonAllocation(id="L_10A_CS_LAB", section_id="s_10a", subject_id="sub_cs_lab", teacher_id="t_lovelace", room_id="lab_cs", periods_per_week=2, block_size=2, sync_group_id="SYNC_G10_PRACTICAL_1", sync_group_name="Grade 10 CS & Chem Lab Pair 1"),
            LessonAllocation(id="L_10A_CHEM_LAB", section_id="s_10a", subject_id="sub_chem_lab", teacher_id="t_curie", room_id="lab_chem", periods_per_week=2, block_size=2, sync_group_id="SYNC_G10_PRACTICAL_2", sync_group_name="Grade 10 Chem & CS Lab Pair 2"),

            # Grade 10 - Section B
            LessonAllocation(id="L_10B_MATH", section_id="s_10b", subject_id="sub_math", teacher_id="t_turing", room_id="r_102", periods_per_week=5, block_size=1),
            LessonAllocation(id="L_10B_ENG", section_id="s_10b", subject_id="sub_eng", teacher_id="t_orwell", room_id="r_102", periods_per_week=4, block_size=1),
            LessonAllocation(id="L_10B_PHY", section_id="s_10b", subject_id="sub_phy", teacher_id="t_newton", room_id="r_102", periods_per_week=4, block_size=1),
            LessonAllocation(id="L_10B_CHEM", section_id="s_10b", subject_id="sub_chem", teacher_id="t_franklin", room_id="r_102", periods_per_week=3, block_size=1),
            LessonAllocation(id="L_10B_BIO", section_id="s_10b", subject_id="sub_bio", teacher_id="t_darwin", room_id="r_102", periods_per_week=3, block_size=1),
            LessonAllocation(id="L_10B_HIST", section_id="s_10b", subject_id="sub_hist", teacher_id="t_orwell", room_id="r_102", periods_per_week=3, block_size=1),
            LessonAllocation(id="L_10B_CS_TH", section_id="s_10b", subject_id="sub_cs", teacher_id="t_lovelace", room_id="r_102", periods_per_week=2, block_size=1),
            LessonAllocation(id="L_10B_PE", section_id="s_10b", subject_id="sub_pe", teacher_id="t_bolt", room_id="ground", periods_per_week=2, block_size=1),
            # Aligned Practicals for Grade 10 Section B (paired with Section A):
            LessonAllocation(id="L_10B_CHEM_LAB", section_id="s_10b", subject_id="sub_chem_lab", teacher_id="t_curie", room_id="lab_chem", periods_per_week=2, block_size=2, sync_group_id="SYNC_G10_PRACTICAL_1", sync_group_name="Grade 10 CS & Chem Lab Pair 1"),
            LessonAllocation(id="L_10B_CS_LAB", section_id="s_10b", subject_id="sub_cs_lab", teacher_id="t_lovelace", room_id="lab_cs", periods_per_week=2, block_size=2, sync_group_id="SYNC_G10_PRACTICAL_2", sync_group_name="Grade 10 Chem & CS Lab Pair 2"),

            # Grade 11 - Section A
            LessonAllocation(id="L_11A_MATH", section_id="s_11a", subject_id="sub_math", teacher_id="t_turing", room_id="r_201", periods_per_week=5, block_size=1),
            LessonAllocation(id="L_11A_ENG", section_id="s_11a", subject_id="sub_eng", teacher_id="t_shakespeare", room_id="r_201", periods_per_week=4, block_size=1),
            LessonAllocation(id="L_11A_PHY", section_id="s_11a", subject_id="sub_phy", teacher_id="t_einstein", room_id="r_201", periods_per_week=4, block_size=1),
            LessonAllocation(id="L_11A_PHY_LAB", section_id="s_11a", subject_id="sub_phy_lab", teacher_id="t_newton", room_id="lab_phy", periods_per_week=2, block_size=2, sync_group_id="SYNC_G11_PRACTICAL_1", sync_group_name="Grade 11 Phy & CS Lab Pair 1"),
            LessonAllocation(id="L_11A_CHEM", section_id="s_11a", subject_id="sub_chem", teacher_id="t_franklin", room_id="r_201", periods_per_week=4, block_size=1),
            LessonAllocation(id="L_11A_CS", section_id="s_11a", subject_id="sub_cs", teacher_id="t_lovelace", room_id="r_201", periods_per_week=3, block_size=1),
            LessonAllocation(id="L_11A_CS_LAB", section_id="s_11a", subject_id="sub_cs_lab", teacher_id="t_lovelace", room_id="lab_cs", periods_per_week=2, block_size=2, sync_group_id="SYNC_G11_PRACTICAL_2", sync_group_name="Grade 11 CS & Phy Lab Pair 2"),
            LessonAllocation(id="L_11A_PE", section_id="s_11a", subject_id="sub_pe", teacher_id="t_bolt", room_id="ground", periods_per_week=2, block_size=1),

            # Grade 11 - Section B
            LessonAllocation(id="L_11B_MATH", section_id="s_11b", subject_id="sub_math", teacher_id="t_turing", room_id="r_202", periods_per_week=5, block_size=1),
            LessonAllocation(id="L_11B_ENG", section_id="s_11b", subject_id="sub_eng", teacher_id="t_shakespeare", room_id="r_202", periods_per_week=4, block_size=1),
            LessonAllocation(id="L_11B_PHY", section_id="s_11b", subject_id="sub_phy", teacher_id="t_newton", room_id="r_202", periods_per_week=4, block_size=1),
            LessonAllocation(id="L_11B_CS_LAB", section_id="s_11b", subject_id="sub_cs_lab", teacher_id="t_lovelace", room_id="lab_cs", periods_per_week=2, block_size=2, sync_group_id="SYNC_G11_PRACTICAL_1", sync_group_name="Grade 11 Phy & CS Lab Pair 1"),
            LessonAllocation(id="L_11B_CHEM", section_id="s_11b", subject_id="sub_chem", teacher_id="t_franklin", room_id="r_202", periods_per_week=4, block_size=1),
            LessonAllocation(id="L_11B_CS", section_id="s_11b", subject_id="sub_cs", teacher_id="t_lovelace", room_id="r_202", periods_per_week=3, block_size=1),
            LessonAllocation(id="L_11B_PHY_LAB", section_id="s_11b", subject_id="sub_phy_lab", teacher_id="t_newton", room_id="lab_phy", periods_per_week=2, block_size=2, sync_group_id="SYNC_G11_PRACTICAL_2", sync_group_name="Grade 11 CS & Phy Lab Pair 2"),
            LessonAllocation(id="L_11B_PE", section_id="s_11b", subject_id="sub_pe", teacher_id="t_bolt", room_id="ground", periods_per_week=2, block_size=1),
        ]
        for a in allocations:
            proj.lessons[a.id] = a

        # Duty Types & Slots
        dt_assembly = DutyType(id="dt_assembly", name="Morning Assembly & Gate Supervision", points_weight=1.0)
        dt_recess = DutyType(id="dt_recess", name="Recess Campus & Corridor Monitoring", points_weight=1.0)
        dt_invigilation = DutyType(id="dt_invigilation", name="Assessment & Exam Invigilation", points_weight=2.0)
        for dt in [dt_assembly, dt_recess, dt_invigilation]:
            proj.duty_types[dt.id] = dt

        duty_slots = [
            DutySlot(id="ds_m_mon", duty_type_id="dt_assembly", duty_name="Morning Assembly", day="Monday", period=0, time_label="08:00 - 08:30", location="Main Ground", required_teachers=2),
            DutySlot(id="ds_m_tue", duty_type_id="dt_assembly", duty_name="Morning Assembly", day="Tuesday", period=0, time_label="08:00 - 08:30", location="Main Ground", required_teachers=2),
            DutySlot(id="ds_m_wed", duty_type_id="dt_assembly", duty_name="Morning Assembly", day="Wednesday", period=0, time_label="08:00 - 08:30", location="Main Ground", required_teachers=2),
            DutySlot(id="ds_m_thu", duty_type_id="dt_assembly", duty_name="Morning Assembly", day="Thursday", period=0, time_label="08:00 - 08:30", location="Main Ground", required_teachers=2),
            DutySlot(id="ds_m_fri", duty_type_id="dt_assembly", duty_name="Morning Assembly", day="Friday", period=0, time_label="08:00 - 08:30", location="Main Ground", required_teachers=2),

            DutySlot(id="ds_r_mon", duty_type_id="dt_recess", duty_name="Recess Corridor Duty", day="Monday", period=4, time_label="11:30 - 12:00", location="Wing A & B Corridors", required_teachers=2),
            DutySlot(id="ds_r_tue", duty_type_id="dt_recess", duty_name="Recess Corridor Duty", day="Tuesday", period=4, time_label="11:30 - 12:00", location="Wing A & B Corridors", required_teachers=2),
            DutySlot(id="ds_r_wed", duty_type_id="dt_recess", duty_name="Recess Corridor Duty", day="Wednesday", period=4, time_label="11:30 - 12:00", location="Wing A & B Corridors", required_teachers=2),
            DutySlot(id="ds_r_thu", duty_type_id="dt_recess", duty_name="Recess Corridor Duty", day="Thursday", period=4, time_label="11:30 - 12:00", location="Wing A & B Corridors", required_teachers=2),
            DutySlot(id="ds_r_fri", duty_type_id="dt_recess", duty_name="Recess Corridor Duty", day="Friday", period=4, time_label="11:30 - 12:00", location="Wing A & B Corridors", required_teachers=2),

            DutySlot(id="ds_inv_wed_p6", duty_type_id="dt_invigilation", duty_name="Mid-Term Hall Invigilation", day="Wednesday", period=6, time_label="Period 6", location="Exam Hall 1", required_teachers=2),
            DutySlot(id="ds_inv_thu_p6", duty_type_id="dt_invigilation", duty_name="Mid-Term Hall Invigilation", day="Thursday", period=6, time_label="Period 6", location="Exam Hall 1", required_teachers=2),
        ]
        for ds in duty_slots:
            proj.duty_slots[ds.id] = ds

        return proj

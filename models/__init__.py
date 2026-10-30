"""
Models package initialization.
"""
from .institution import InstitutionSettings, PeriodTime
from .subject import Subject, PALETTE_COLORS, ROOM_TYPES
from .teacher import Teacher
from .classroom import Classroom
from .section import GradeClass, Section
from .lesson import LessonAllocation, ScheduledSlot
from .duty import DutyType, DutySlot, DutyAssignment
from .timetable_data import TimetableProject

__all__ = [
    "InstitutionSettings",
    "PeriodTime",
    "Subject",
    "PALETTE_COLORS",
    "ROOM_TYPES",
    "Teacher",
    "Classroom",
    "GradeClass",
    "Section",
    "LessonAllocation",
    "ScheduledSlot",
    "DutyType",
    "DutySlot",
    "DutyAssignment",
    "TimetableProject"
]

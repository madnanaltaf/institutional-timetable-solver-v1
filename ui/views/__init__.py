"""
UI Views package initialization.
"""
from .dashboard_view import DashboardView
from .institution_view import InstitutionView
from .teachers_view import TeachersView
from .classes_view import ClassesView
from .rooms_view import RoomsView
from .subjects_view import SubjectsView
from .lessons_view import LessonsView
from .timetable_view import TimetableView
from .duty_roster_view import DutyRosterView
from .export_view import ExportView

__all__ = [
    "DashboardView",
    "InstitutionView",
    "TeachersView",
    "ClassesView",
    "RoomsView",
    "SubjectsView",
    "LessonsView",
    "TimetableView",
    "DutyRosterView",
    "ExportView"
]

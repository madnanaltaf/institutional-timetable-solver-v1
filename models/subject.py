"""
Subject Model
Defines subjects, lab requirements, color codes, and difficulty ratings.
"""
from dataclasses import dataclass, asdict
from typing import Dict, Any

PALETTE_COLORS = [
    "#3B82F6",  # Blue
    "#10B981",  # Emerald / Green
    "#F59E0B",  # Amber / Orange
    "#8B5CF6",  # Purple
    "#EC4899",  # Pink
    "#06B6D4",  # Cyan
    "#EF4444",  # Red
    "#14B8A6",  # Teal
    "#6366F1",  # Indigo
    "#84CC16",  # Lime
    "#F97316",  # Deep Orange
    "#64748B",  # Slate
]

ROOM_TYPES = [
    "General Classroom",
    "Computer Lab",
    "Chemistry Lab",
    "Physics Lab",
    "Biology Lab",
    "Auditorium / Hall",
    "Library",
    "Sports Ground / Gym"
]

@dataclass
class Subject:
    id: str
    code: str
    name: str
    subject_type: str = "Theory"  # Theory, Practical Lab, Elective, PE, Activity
    color: str = "#3B82F6"
    requires_lab: bool = False
    default_room_type: str = "General Classroom"
    is_difficult: bool = False  # E.g. Math, Physics -> for fatigue avoidance
    allowed_double_period: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Subject":
        return cls(**data)

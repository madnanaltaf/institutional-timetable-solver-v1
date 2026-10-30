"""
Class & Section Model
Represents grade levels and multi-section classes with capacities and home rooms.
"""
from dataclasses import dataclass, asdict
from typing import Dict, Any

@dataclass
class GradeClass:
    id: str
    name: str  # e.g., "Grade 10", "Grade 11", "First Year Pre-Eng"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GradeClass":
        return cls(**data)


@dataclass
class Section:
    id: str
    class_id: str
    class_name: str
    name: str  # e.g., "A", "B", "Section A"
    student_count: int = 35
    home_room_id: str = ""  # Default base classroom
    class_teacher_id: str = ""  # Designated Class Teacher / Incharge

    @property
    def display_name(self) -> str:
        return f"{self.class_name} - {self.name}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "name": self.name,
            "student_count": self.student_count,
            "home_room_id": self.home_room_id,
            "class_teacher_id": self.class_teacher_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Section":
        cleaned = dict(data)
        cleaned.setdefault("class_teacher_id", "")
        return cls(**cleaned)

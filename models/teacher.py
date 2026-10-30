"""
Teacher Model
Defines instructors, workloads, subject qualifications, and availability constraints.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Tuple, Dict, Any

@dataclass
class Teacher:
    id: str
    name: str
    code: str  # Short code for compact grid views, e.g., "SC", "ALT"
    email: str = ""
    phone: str = ""
    primary_subject_id: str = ""  # The single specialized subject field this teacher teaches
    qualified_subjects: List[str] = field(default_factory=list)  # Subject IDs
    max_periods_per_week: int = 24
    max_periods_per_day: int = 5
    max_consecutive_periods: int = 3
    unavailable_slots: List[List[Any]] = field(default_factory=list)  # [[day_str, period_int], ...]
    color: str = "#4F46E5"

    def __post_init__(self):
        if self.primary_subject_id and self.primary_subject_id not in self.qualified_subjects:
            self.qualified_subjects.append(self.primary_subject_id)
        elif not self.primary_subject_id and self.qualified_subjects:
            self.primary_subject_id = self.qualified_subjects[0]

    def set_single_subject(self, subject_id: str):
        """Sets the single specialized subject this teacher teaches in school."""
        self.primary_subject_id = subject_id
        self.qualified_subjects = [subject_id] if subject_id else []

    def teaches_subject(self, subject_id: str) -> bool:
        if self.primary_subject_id:
            return self.primary_subject_id == subject_id
        return subject_id in self.qualified_subjects

    def is_available(self, day: str, period: int) -> bool:
        for u in self.unavailable_slots:
            if len(u) >= 2 and u[0] == day and u[1] == period:
                return False
        return True

    def add_unavailable_slot(self, day: str, period: int):
        if not self.is_unavailable(day, period):
            self.unavailable_slots.append([day, period])

    def remove_unavailable_slot(self, day: str, period: int):
        self.unavailable_slots = [
            u for u in self.unavailable_slots
            if not (len(u) >= 2 and u[0] == day and u[1] == period)
        ]

    def is_unavailable(self, day: str, period: int) -> bool:
        return not self.is_available(day, period)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Teacher":
        cleaned = dict(data)
        cleaned.setdefault("primary_subject_id", "")
        return cls(**cleaned)

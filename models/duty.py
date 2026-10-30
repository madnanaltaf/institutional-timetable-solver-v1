"""
Duty Roster & Invigilation Models
Handles campus duty slots, invigilation demands, and teacher assignment rosters.
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List

@dataclass
class DutyType:
    id: str
    name: str  # e.g., "Exam Invigilation", "Morning Assembly", "Recess Duty"
    points_weight: float = 1.0  # Weight for fairness balancing

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DutyType":
        return cls(**data)


@dataclass
class DutySlot:
    id: str
    duty_type_id: str
    duty_name: str
    day: str
    period: int  # 0 = Before Period 1 (Morning), -1 = Recess/Break, or 1..N for specific period
    time_label: str = ""
    location: str = "Campus Premises"
    required_teachers: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DutySlot":
        return cls(**data)


@dataclass
class DutyAssignment:
    id: str
    duty_slot_id: str
    teacher_id: str
    teacher_name: str
    day: str
    period: int
    duty_name: str
    location: str
    time_label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DutyAssignment":
        return cls(**data)

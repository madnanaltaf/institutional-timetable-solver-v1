"""
Lesson Allocation & Scheduled Slot Models
Handles curriculum allocations, block sizes, and parallel synchronized practical groups.
"""
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional

@dataclass
class LessonAllocation:
    """
    Represents a curriculum requirement:
    e.g., Grade 10-A takes 4 periods of Math per week with Dr. Smith in Room 101.
    """
    id: str
    section_id: str
    subject_id: str
    teacher_id: str
    room_id: str = ""  # If empty, solver picks available room matching subject's default room type
    periods_per_week: int = 4
    block_size: int = 1  # 1 = single period, 2 = 2-period lab block, 3 = 3-period block
    sync_group_id: str = ""  # Parallel group tag (e.g. for simultaneous CS Lab Sec A & Chem Lab Sec B)
    sync_group_name: str = ""
    combined_group_id: str = ""  # All-sections session tag (same lesson taught to every section of a class)
    all_sections: bool = False  # True when this lesson is part of a combined all-sections session
    priority: int = 3  # 1 to 5 (5 highest)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LessonAllocation":
        return cls(**data)


@dataclass
class ScheduledSlot:
    """
    Represents an assigned period in the generated timetable.
    """
    id: str
    lesson_id: str
    section_id: str
    subject_id: str
    teacher_id: str
    room_id: str
    day: str
    period: int
    duration: int = 1  # 1 for single period, 2 for double block
    sync_group_id: str = ""
    combined_group_id: str = ""
    all_sections: bool = False
    is_locked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScheduledSlot":
        return cls(
            id=data["id"],
            lesson_id=data["lesson_id"],
            section_id=data["section_id"],
            subject_id=data["subject_id"],
            teacher_id=data["teacher_id"],
            room_id=data.get("room_id", ""),
            day=data["day"],
            period=data["period"],
            duration=data.get("duration", 1),
            sync_group_id=data.get("sync_group_id", ""),
            combined_group_id=data.get("combined_group_id", ""),
            all_sections=data.get("all_sections", False),
            is_locked=data.get("is_locked", False)
        )

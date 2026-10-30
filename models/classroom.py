"""
Classroom & Laboratory Model
Defines rooms, specialized labs, capacity, and building locations.
"""
from dataclasses import dataclass, asdict
from typing import Dict, Any

@dataclass
class Classroom:
    id: str
    name: str
    room_type: str = "General Classroom"
    capacity: int = 40
    building: str = "Main Academic Wing"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Classroom":
        return cls(**data)

"""
Institution Settings Model
Defines working days, period timings, breaks, and academic info.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

DEFAULT_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

@dataclass
class PeriodTime:
    period_num: int
    name: str = ""
    start_time: str = "08:00"
    end_time: str = "08:45"
    is_break: bool = False
    break_label: str = ""

    def __post_init__(self):
        if not self.name:
            if self.is_break:
                self.name = self.break_label or "Break / Recess"
            else:
                self.name = f"Period {self.period_num}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PeriodTime":
        return cls(**data)


@dataclass
class InstitutionSettings:
    name: str = "National Science & Arts Institute"
    academic_year: str = "2026 - 2027"
    term: str = "Fall Semester"
    motto: str = "Excellence Through Knowledge"
    working_days: List[str] = field(default_factory=lambda: list(DEFAULT_DAYS))
    periods_per_day: int = 7
    friday_periods: int = 4  # Fewer periods on Friday (e.g. half-day / prayer break)
    day_periods: Dict[str, int] = field(default_factory=dict)  # Optional custom periods per day
    period_times: List[PeriodTime] = field(default_factory=list)
    break_after_period: int = 4  # Default recess after period 4
    break_duration_mins: int = 30
    period_duration_mins: int = 45
    start_hour: int = 8
    start_min: int = 30

    def __post_init__(self):
        if not self.day_periods:
            self.day_periods = {"Friday": self.friday_periods}
        elif "Friday" in self.day_periods:
            self.friday_periods = self.day_periods["Friday"]
        if not self.period_times:
            self.generate_default_period_times()

    def get_periods_for_day(self, day: str) -> int:
        """Returns the number of active periods for a specific day (e.g. Friday has fewer periods)."""
        if self.day_periods and day in self.day_periods:
            return self.day_periods[day]
        if day.lower() == "friday" and self.friday_periods > 0:
            return self.friday_periods
        return self.periods_per_day

    def get_max_periods_any_day(self) -> int:
        """Returns the maximum number of periods across all working days."""
        max_p = self.periods_per_day
        if self.day_periods:
            max_p = max([max_p] + list(self.day_periods.values()))
        return max_p

    def get_total_weekly_slots(self) -> int:
        """Returns total active slot capacity across all working days."""
        return sum(self.get_periods_for_day(d) for d in self.working_days)

    def generate_default_period_times(self):
        """Generates realistic period timing intervals based on configuration."""
        self.period_times = []
        cur_minute = self.start_hour * 60 + self.start_min
        max_p = self.get_max_periods_any_day()
        for p in range(1, max_p + 1):
            start_str = f"{cur_minute // 60:02d}:{cur_minute % 60:02d}"
            cur_minute += self.period_duration_mins
            end_str = f"{cur_minute // 60:02d}:{cur_minute % 60:02d}"
            self.period_times.append(
                PeriodTime(
                    period_num=p,
                    name=f"Period {p}",
                    start_time=start_str,
                    end_time=end_str,
                    is_break=False
                )
            )
            if p == self.break_after_period and p < max_p:
                cur_minute += self.break_duration_mins

    def get_period_label(self, p_num: int) -> str:
        for pt in self.period_times:
            if pt.period_num == p_num:
                return f"P{p_num} ({pt.start_time}-{pt.end_time})"
        return f"Period {p_num}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "academic_year": self.academic_year,
            "term": self.term,
            "motto": self.motto,
            "working_days": list(self.working_days),
            "periods_per_day": self.periods_per_day,
            "friday_periods": self.friday_periods,
            "day_periods": dict(self.day_periods),
            "period_times": [pt.to_dict() for pt in self.period_times],
            "break_after_period": self.break_after_period,
            "break_duration_mins": self.break_duration_mins,
            "period_duration_mins": self.period_duration_mins,
            "start_hour": self.start_hour,
            "start_min": self.start_min
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "InstitutionSettings":
        period_times_raw = data.get("period_times", [])
        period_times = [PeriodTime.from_dict(pt) for pt in period_times_raw]
        cleaned = dict(data)
        cleaned["period_times"] = period_times
        cleaned.setdefault("friday_periods", 4)
        cleaned.setdefault("day_periods", {"Friday": cleaned["friday_periods"]})
        return cls(**cleaned)

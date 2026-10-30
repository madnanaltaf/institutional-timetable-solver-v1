"""
Interactive Slot Editor & Manual Swap Dialog
Allows administrators to manually adjust or swap time slots with real-time conflict checking.
"""
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox

from models.timetable_data import TimetableProject
from models.lesson import ScheduledSlot

class EditSlotDialog(tb.Toplevel):
    def __init__(self, parent, project: TimetableProject, slot: ScheduledSlot, on_changed=None):
        super().__init__(parent)
        self.project = project
        self.slot = slot
        self.on_changed = on_changed

        sub = self.project.subjects.get(slot.subject_id)
        sub_name = sub.name if sub else slot.subject_id
        sec = self.project.sections.get(slot.section_id)
        sec_name = sec.display_name if sec else slot.section_id

        self.title(f"Edit Timetable Slot - {sec_name} ({sub_name})")
        self.geometry("480x420")
        self.resizable(False, False)

        self._build_ui()

    def _build_ui(self):
        hdr = tb.Frame(self, bootstyle="primary", padding=12)
        hdr.pack(fill=X)

        sub = self.project.subjects.get(self.slot.subject_id)
        teacher = self.project.teachers.get(self.slot.teacher_id)
        sec = self.project.sections.get(self.slot.section_id)
        room = self.project.classrooms.get(self.slot.room_id)

        tb.Label(
            hdr,
            text=f"{sec.display_name if sec else ''} — {sub.name if sub else ''}",
            font=("Helvetica", 12, "bold"),
            bootstyle="inverse-primary"
        ).pack(anchor=W)

        tb.Label(
            hdr,
            text=f"Teacher: {teacher.name if teacher else ''}  |  Location: {room.name if room else ''}  |  Duration: {self.slot.duration} period(s)",
            font=("Helvetica", 8),
            bootstyle="inverse-primary"
        ).pack(anchor=W)

        content = tb.Frame(self, padding=20)
        content.pack(fill=BOTH, expand=True)

        tb.Label(content, text="Move to New Time Slot:", font=("Helvetica", 10, "bold")).pack(anchor=W, pady=(0, 10))

        grid = tb.Frame(content)
        grid.pack(fill=X, pady=(0, 10))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        tb.Label(grid, text="Select Day:").grid(row=0, column=0, sticky=W, pady=4)
        days = list(self.project.institution.working_days)
        self.combo_day = tb.Combobox(grid, values=days, state="readonly")
        self.combo_day.set(self.slot.day)
        self.combo_day.grid(row=0, column=1, sticky="ew", pady=4)
        self.combo_day.bind("<<ComboboxSelected>>", self._on_day_changed)

        tb.Label(grid, text="Select Period:").grid(row=1, column=0, sticky=W, pady=4)
        self.combo_period = tb.Combobox(grid, state="readonly")
        self.combo_period.grid(row=1, column=1, sticky="ew", pady=4)
        self._refresh_periods_for_day(self.slot.day, self.slot.period)
        self.combo_period.bind("<<ComboboxSelected>>", self._validate_slot)

        tb.Label(grid, text="Assigned Faculty:").grid(row=2, column=0, sticky=W, pady=4)
        cur_t = self.project.teachers.get(self.slot.teacher_id)
        cur_sub = self.project.subjects.get(self.slot.subject_id)
        teach_options = []
        for t in self.project.teachers.values():
            is_spec = (cur_sub and t.teaches_subject(cur_sub.id))
            star = "⭐ " if is_spec else ""
            teach_options.append(f"{star}{t.name} ({t.code}) [{t.id}]")
        self.combo_teacher = tb.Combobox(grid, values=teach_options, state="readonly")
        initial_t_str = f"{'⭐ ' if cur_t and cur_sub and cur_t.teaches_subject(cur_sub.id) else ''}{cur_t.name if cur_t else ''} ({cur_t.code if cur_t else ''}) [{self.slot.teacher_id}]"
        self.combo_teacher.set(initial_t_str)
        self.combo_teacher.grid(row=2, column=1, sticky="ew", pady=4)
        self.combo_teacher.bind("<<ComboboxSelected>>", self._validate_slot)

        # Real-time conflict feedback card
        self.conflict_card = tb.Labelframe(content, text=" Conflict Validation ", bootstyle="secondary", padding=10)
        self.conflict_card.pack(fill=BOTH, expand=True, pady=(10, 15))

        self.lbl_conflict_status = tb.Label(
            self.conflict_card,
            text="Checking slot...",
            font=("Helvetica", 9),
            wraplength=400
        )
        self.lbl_conflict_status.pack(anchor=W)

        # Buttons
        btn_box = tb.Frame(content)
        btn_box.pack(fill=X)

        self.btn_apply = tb.Button(btn_box, text="💾 Apply Changes", bootstyle="success", command=self._on_apply)
        self.btn_apply.pack(side=RIGHT, padx=5)

        tb.Button(btn_box, text="Cancel", bootstyle="secondary-outline", command=self.destroy).pack(side=RIGHT)

        self._validate_slot(None)

    def _refresh_periods_for_day(self, day: str, target_p: int = 1):
        day_max = self.project.institution.get_periods_for_day(day)
        periods = [f"Period {p}" for p in range(1, day_max - self.slot.duration + 2)]
        self.combo_period['values'] = periods
        if f"Period {target_p}" in periods:
            self.combo_period.set(f"Period {target_p}")
        elif periods:
            self.combo_period.set(periods[0])

    def _on_day_changed(self, event):
        target_day = self.combo_day.get()
        p_str = self.combo_period.get()
        try:
            cur_p = int(p_str.replace("Period", "").strip())
        except ValueError:
            cur_p = 1
        self._refresh_periods_for_day(target_day, cur_p)
        self._validate_slot(None)

    def _parse_id(self, text: str) -> str:
        if "[" in text and text.endswith("]"):
            return text.split("[")[-1].rstrip("]")
        return ""

    def _validate_slot(self, event):
        target_day = self.combo_day.get()
        p_str = self.combo_period.get()
        target_teacher_id = self._parse_id(self.combo_teacher.get()) or self.slot.teacher_id

        try:
            target_period = int(p_str.replace("Period", "").strip())
        except ValueError:
            return

        conflicts = []

        # 0. Friday / Day period bounds check
        day_max = self.project.institution.get_periods_for_day(target_day)
        if target_period + self.slot.duration - 1 > day_max:
            conflicts.append(f"Exceeds {target_day}'s limit ({day_max} periods max due to early dismissal).")

        # 1. Recess check
        break_after = self.project.institution.break_after_period
        if self.slot.duration > 1:
            if target_period <= break_after < target_period + self.slot.duration:
                conflicts.append("Cannot span multi-period block across recess break.")

        # 2. Check collision with other slots
        for s in self.project.schedule:
            if s.id == self.slot.id:
                continue

            # Does slot s overlap with target_period..target_period + duration?
            if s.day == target_day:
                s_end = s.period + s.duration
                target_end = target_period + self.slot.duration

                overlap = not (target_end <= s.period or target_period >= s_end)
                if overlap:
                    if s.section_id == self.slot.section_id:
                        sub = self.project.subjects.get(s.subject_id)
                        conflicts.append(f"Section conflict: Section already taking '{sub.name if sub else s.subject_id}'.")
                    if s.teacher_id == target_teacher_id:
                        sec = self.project.sections.get(s.section_id)
                        conflicts.append(f"Teacher conflict: Selected teacher is teaching '{sec.display_name if sec else s.section_id}'.")
                    if s.room_id and s.room_id == self.slot.room_id:
                        room = self.project.classrooms.get(s.room_id)
                        conflicts.append(f"Room conflict: '{room.name if room else s.room_id}' is occupied.")

        # 3. Teacher unavailability check
        teacher = self.project.teachers.get(target_teacher_id)
        if teacher:
            for p in range(target_period, target_period + self.slot.duration):
                if not teacher.is_available(target_day, p):
                    conflicts.append(f"Teacher '{teacher.name}' is marked unavailable on {target_day} P{p}.")

        if conflicts:
            msg = "⚠️ Conflicts detected:\n" + "\n".join([f"• {c}" for c in conflicts])
            self.lbl_conflict_status.config(text=msg, bootstyle="danger")
            self.btn_apply.config(state="disabled")
        else:
            self.lbl_conflict_status.config(
                text="✓ Target slot and teacher are completely free and conflict-free!",
                bootstyle="success"
            )
            self.btn_apply.config(state="normal")

    def _on_apply(self):
        target_day = self.combo_day.get()
        p_str = self.combo_period.get()
        target_teacher_id = self._parse_id(self.combo_teacher.get()) or self.slot.teacher_id

        try:
            target_period = int(p_str.replace("Period", "").strip())
        except ValueError:
            return

        self.slot.day = target_day
        self.slot.period = target_period
        self.slot.teacher_id = target_teacher_id

        if self.on_changed:
            self.on_changed()

        messagebox.showinfo("Slot Updated", "Timetable slot and faculty assignment updated successfully!")
        self.destroy()

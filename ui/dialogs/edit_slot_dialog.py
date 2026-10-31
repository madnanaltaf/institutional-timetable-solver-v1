"""
Interactive Slot Editor & Manual Swap Dialog
Allows administrators to manually adjust or swap time slots with real-time conflict checking.
"""
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox

from models.timetable_data import TimetableProject
from models.lesson import ScheduledSlot
from solver.validator import ProjectValidator

class EditSlotDialog(tb.Toplevel):
    def __init__(self, parent, project: TimetableProject, slot: ScheduledSlot, on_changed=None):
        super().__init__(parent)
        self.project = project
        self.slot = slot
        self.on_changed = on_changed
        self.group = project.get_alignment_group(slot)

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

        if len(self.group) > 1:
            tb.Label(
                content,
                text=f"🔗 This lecture is aligned with {len(self.group) - 1} other section(s) — they move together.",
                font=("Helvetica", 9, "bold"),
                bootstyle="info",
                wraplength=430
            ).pack(anchor=W, pady=(0, 8))

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

        # Lock / Pin in place toggle
        lock_box = tb.Frame(content)
        lock_box.pack(fill=X, pady=(0, 10))
        self.var_locked = tb.BooleanVar(value=getattr(self.slot, 'is_locked', False))
        self.chk_locked = tb.Checkbutton(
            lock_box,
            text="🔒 Lock this lecture in place (Pinned — Re-generating solver will never move it)",
            variable=self.var_locked,
            bootstyle="warning-round-toggle"
        )
        self.chk_locked.pack(anchor=W)

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

    def _apply_target(self, target_day: str, target_period: int, target_teacher_id: str):
        """Temporarily moves the aligned group. Returns the original state for rollback."""
        originals = []
        for s in self.group:
            originals.append((s, s.day, s.period, s.teacher_id))
            s.day = target_day
            s.period = target_period
            if s.id == self.slot.id or s.combined_group_id:
                s.teacher_id = target_teacher_id
        return originals

    @staticmethod
    def _restore_group(originals):
        for s, day, period, teacher_id in originals:
            s.day = day
            s.period = period
            s.teacher_id = teacher_id

    def _collect_conflicts(self, target_day: str, target_period: int, target_teacher_id: str):
        originals = self._apply_target(target_day, target_period, target_teacher_id)
        issues = [
            i for i in ProjectValidator(self.project).validate_schedule()
            if i.severity == "ERROR"
        ]
        self._restore_group(originals)
        return issues

    def _validate_slot(self, event):
        target_day = self.combo_day.get()
        p_str = self.combo_period.get()
        target_teacher_id = self._parse_id(self.combo_teacher.get()) or self.slot.teacher_id

        try:
            target_period = int(p_str.replace("Period", "").strip())
        except ValueError:
            return

        issues = self._collect_conflicts(target_day, target_period, target_teacher_id)
        if issues:
            msg = "⚠️ Conflicts detected:\n" + "\n".join(f"• {i.description}" for i in issues)
            self.lbl_conflict_status.config(text=msg, bootstyle="danger")
            self.btn_apply.config(state="disabled")
        else:
            extra = (
                f"\n\n🔗 {len(self.group) - 1} aligned section(s) will move with this lecture."
                if len(self.group) > 1 else ""
            )
            self.lbl_conflict_status.config(
                text="✓ Target slot and teacher are completely free and conflict-free!" + extra,
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

        issues = self._collect_conflicts(target_day, target_period, target_teacher_id)
        if issues:
            messagebox.showerror(
                "Cannot Move Lecture",
                "The move would create conflict(s):\n\n" + "\n".join(f"• {i.description}" for i in issues[:8])
            )
            return

        self._apply_target(target_day, target_period, target_teacher_id)
        lock_state = bool(self.var_locked.get())
        for s in self.group:
            s.is_locked = lock_state

        if self.on_changed:
            self.on_changed()

        messagebox.showinfo("Slot Updated", "Timetable slot and faculty assignment updated successfully!")
        self.destroy()

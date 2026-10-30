"""
Interactive Timetable Explorer View
Renders multi-dimensional timetable grids (Section, Teacher, Room, and Master Matrix)
with color-coded subject cards, aligned practical badges, and click-to-edit capabilities.
"""
import os
import threading
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox, filedialog

from models.timetable_data import TimetableProject
from models.lesson import ScheduledSlot
from solver.timetable_solver import TimetableSolver
from solver.duty_solver import DutyRosterSolver
from ui.dialogs.edit_slot_dialog import EditSlotDialog
from exports.pdf_generator import TimetablePDFGenerator

VIEW_MODES = ["Section / Class View", "Faculty Teacher View", "Room / Laboratory View", "Master Class Matrix (By Day)", "Master Faculty Matrix (By Day)"]

class TimetableView(tb.Frame):
    def __init__(self, parent, project: TimetableProject, on_update_callback=None):
        super().__init__(parent)
        self.project = project
        self.on_update_callback = on_update_callback

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Header Controls Bar
        header = tb.Frame(self)
        header.pack(fill=X, padx=20, pady=(15, 10))

        tb.Label(header, text="Interactive Timetable Grid Explorer", font=("Helvetica", 16, "bold"), bootstyle="primary").pack(side=LEFT)

        controls = tb.Frame(header)
        controls.pack(side=RIGHT)

        # Prominent Generate Button right in the timetable view!
        self.btn_gen_header = tb.Button(
            controls,
            text="⚡ Generate Timetable",
            bootstyle="success",
            command=self._on_generate_timetable
        )
        self.btn_gen_header.pack(side=LEFT, padx=(0, 10))

        # Quick Export Button
        self.btn_export_quick = tb.Button(
            controls,
            text="📄 Export to PDF",
            bootstyle="info-outline",
            command=self._on_quick_export
        )
        self.btn_export_quick.pack(side=LEFT, padx=(0, 15))

        tb.Label(controls, text="View Mode:").pack(side=LEFT, padx=(0, 4))
        self.combo_mode = tb.Combobox(controls, values=VIEW_MODES, state="readonly", width=22)
        self.combo_mode.set(VIEW_MODES[0])
        self.combo_mode.pack(side=LEFT, padx=(0, 10))
        self.combo_mode.bind("<<ComboboxSelected>>", self._on_mode_change)

        self.lbl_filter = tb.Label(controls, text="Select:")
        self.lbl_filter.pack(side=LEFT, padx=(0, 4))
        self.combo_filter = tb.Combobox(controls, state="readonly", width=24)
        self.combo_filter.pack(side=LEFT, padx=(0, 10))
        self.combo_filter.bind("<<ComboboxSelected>>", lambda e: self._render_grid())

        self.btn_refresh = tb.Button(controls, text="🔄 Refresh", bootstyle="secondary-outline", command=self.refresh)
        self.btn_refresh.pack(side=LEFT)

        self.btn_lock_all = tb.Button(
            controls,
            text="🔒 Lock All",
            bootstyle="warning-outline",
            command=lambda: self._lock_all_slots(True)
        )
        self.btn_lock_all.pack(side=LEFT, padx=(6, 2))

        self.btn_unlock_all = tb.Button(
            controls,
            text="🔓 Unlock All",
            bootstyle="secondary-outline",
            command=lambda: self._lock_all_slots(False)
        )
        self.btn_unlock_all.pack(side=LEFT, padx=(0, 6))

        # Scrollable Grid Container
        self.grid_canvas_frame = tb.Frame(self)
        self.grid_canvas_frame.pack(fill=BOTH, expand=True, padx=20, pady=(0, 15))

        self.grid_container = tb.Frame(self.grid_canvas_frame)
        self.grid_container.pack(fill=BOTH, expand=True)

    def refresh(self):
        """Refreshes filter options and re-renders grid."""
        self._on_mode_change(None)

    def _on_mode_change(self, event):
        mode = self.combo_mode.get()

        if mode == "Section / Class View":
            self.lbl_filter.config(text="Select Section:")
            items = [f"{s.display_name} [{s.id}]" for s in self.project.sections.values()]
            self.combo_filter['values'] = items
            if items:
                self.combo_filter.set(items[0])
        elif mode == "Faculty Teacher View":
            self.lbl_filter.config(text="Select Faculty:")
            items = [f"{t.name} ({t.code}) [{t.id}]" for t in self.project.teachers.values()]
            self.combo_filter['values'] = items
            if items:
                self.combo_filter.set(items[0])
        elif mode == "Room / Laboratory View":
            self.lbl_filter.config(text="Select Facility:")
            items = [f"{r.name} ({r.room_type}) [{r.id}]" for r in self.project.classrooms.values()]
            self.combo_filter['values'] = items
            if items:
                self.combo_filter.set(items[0])
        else:  # Master Matrix
            self.lbl_filter.config(text="Select Day:")
            items = list(self.project.institution.working_days)
            self.combo_filter['values'] = items
            if items:
                self.combo_filter.set(items[0])

        self._render_grid()

    def _parse_id(self, text: str) -> str:
        if "[" in text and text.endswith("]"):
            return text.split("[")[-1].rstrip("]")
        return ""

    def _render_grid(self):
        for widget in self.grid_container.winfo_children():
            widget.destroy()

        if not self.project.is_generated or not self.project.schedule:
            # Welcoming, actionable empty state card with prominent generate buttons!
            no_sched_frame = tb.Labelframe(
                self.grid_container,
                text=" ⚡ Timetable Not Generated Yet ",
                bootstyle="info",
                padding=30
            )
            no_sched_frame.pack(fill=BOTH, expand=True, padx=40, pady=40)

            tb.Label(
                no_sched_frame,
                text="Ready to Solve & Generate Institutional Timetable!",
                font=("Helvetica", 16, "bold"),
                bootstyle="primary"
            ).pack(pady=(10, 8))

            tb.Label(
                no_sched_frame,
                text="Click the button below to solve all constraints (teacher double-booking, room capacity, parallel science practicals, and cognitive fatigue).",
                font=("Helvetica", 10),
                bootstyle="secondary"
            ).pack(pady=(0, 20))

            btn_box = tb.Frame(no_sched_frame)
            btn_box.pack(pady=10)

            tb.Button(
                btn_box,
                text="⚡ GENERATE TIMETABLE NOW (1-CLICK)",
                bootstyle="success",
                padding=12,
                command=self._on_generate_timetable
            ).pack(side=LEFT, padx=10)

            tb.Button(
                btn_box,
                text="🚀 Load Sample College Data & Generate",
                bootstyle="info-outline",
                padding=12,
                command=self._on_load_sample_and_generate
            ).pack(side=LEFT, padx=10)

            # Quick summary of current inputs
            stats_frame = tb.Frame(no_sched_frame)
            stats_frame.pack(pady=(25, 0))

            tb.Label(
                stats_frame,
                text=f"Current Project: {self.project.institution.name}  |  Sections: {len(self.project.sections)}  |  Teachers: {len(self.project.teachers)}  |  Lessons: {len(self.project.lessons)}",
                font=("Helvetica", 9, "italic"),
                bootstyle="secondary"
            ).pack()
            return

        mode = self.combo_mode.get()
        if mode == "Section / Class View":
            self._render_section_view()
        elif mode == "Faculty Teacher View":
            self._render_teacher_view()
        elif mode == "Room / Laboratory View":
            self._render_room_view()
        elif mode == "Master Faculty Matrix (By Day)":
            self._render_master_faculty_matrix_view()
        else:
            self._render_master_matrix_view()

    # ------------------ 1. Section View ------------------ #
    def _render_section_view(self):
        sec_id = self._parse_id(self.combo_filter.get())
        if not sec_id:
            return

        sec = self.project.sections.get(sec_id)
        
        top_bar = tb.Frame(self.grid_container)
        top_bar.grid(row=0, column=0, columnspan=12, sticky="ew", pady=(0, 6))

        incharge_text = ""
        if sec and sec.class_teacher_id:
            t_incharge = self.project.teachers.get(sec.class_teacher_id)
            if t_incharge:
                incharge_text = f"👨‍🏫 Class Incharge: {t_incharge.name} ({t_incharge.code})  |  Strength: {sec.student_count} Students"

        if incharge_text:
            tb.Label(top_bar, text=incharge_text, font=("Helvetica", 10, "bold"), bootstyle="primary").pack(side=LEFT)

        sec_btn_box = tb.Frame(top_bar)
        sec_btn_box.pack(side=RIGHT)
        tb.Button(sec_btn_box, text="🔒 Lock All in Section", bootstyle="warning-outline", padding=(6, 2), command=lambda: self._toggle_section_lock(sec_id, True)).pack(side=LEFT, padx=(0, 5))
        tb.Button(sec_btn_box, text="🔓 Unlock Section", bootstyle="secondary-outline", padding=(6, 2), command=lambda: self._toggle_section_lock(sec_id, False)).pack(side=LEFT)

        days = list(self.project.institution.working_days)
        periods_count = self.project.institution.get_max_periods_any_day()
        break_after = self.project.institution.break_after_period

        start_row = 1

        # Header Row: Days by row, Periods by column!
        col_idx = 0
        tb.Label(self.grid_container, text="Day / Timing", font=("Helvetica", 9, "bold"), bootstyle="inverse-primary", padding=6).grid(row=start_row, column=col_idx, sticky="nsew", padx=1, pady=1)
        col_idx += 1

        for p in range(1, break_after + 1):
            time_lbl = self.project.institution.get_period_label(p)
            tb.Label(self.grid_container, text=time_lbl, font=("Helvetica", 9, "bold"), bootstyle="inverse-primary", padding=6).grid(row=start_row, column=col_idx, sticky="nsew", padx=1, pady=1)
            col_idx += 1

        # Break Column
        tb.Label(self.grid_container, text="RECESS\n11:00-11:30", font=("Helvetica", 8, "bold"), bootstyle="warning", padding=6).grid(row=start_row, column=col_idx, sticky="nsew", padx=1, pady=1)
        col_idx += 1

        for p in range(break_after + 1, periods_count + 1):
            time_lbl = self.project.institution.get_period_label(p)
            tb.Label(self.grid_container, text=time_lbl, font=("Helvetica", 9, "bold"), bootstyle="inverse-primary", padding=6).grid(row=start_row, column=col_idx, sticky="nsew", padx=1, pady=1)
            col_idx += 1

        total_cols = col_idx

        # Day Rows
        for r_idx, day in enumerate(days, start=start_row + 1):
            col = 0
            fri_lbl = "\n(4 Periods)" if day == "Friday" else ""
            tb.Label(self.grid_container, text=f"{day}{fri_lbl}", font=("Helvetica", 9, "bold"), bootstyle="secondary", padding=6).grid(row=r_idx, column=col, sticky="nsew", padx=1, pady=1)
            col += 1

            day_max_p = self.project.institution.get_periods_for_day(day)

            # Periods 1 to break_after
            for p in range(1, break_after + 1):
                slot = self.project.get_slot_at(day, p, sec_id)
                self._create_cell_card(self.grid_container, slot, r_idx, col, context="section")
                col += 1

            # Recess Column
            tb.Label(self.grid_container, text="☕ RECESS", font=("Helvetica", 8, "bold"), bootstyle="warning-outline", padding=4).grid(row=r_idx, column=col, sticky="nsew", padx=1, pady=1)
            col += 1

            # Periods after break
            for p in range(break_after + 1, periods_count + 1):
                if p > day_max_p:
                    tb.Label(self.grid_container, text="— Dismissal —", font=("Helvetica", 8, "italic"), bootstyle="secondary-outline", padding=6).grid(row=r_idx, column=col, sticky="nsew", padx=1, pady=1)
                else:
                    slot = self.project.get_slot_at(day, p, sec_id)
                    self._create_cell_card(self.grid_container, slot, r_idx, col, context="section")
                col += 1

        for c in range(total_cols):
            self.grid_container.columnconfigure(c, weight=1)

    # ------------------ 2. Teacher View ------------------ #
    def _render_teacher_view(self):
        t_id = self._parse_id(self.combo_filter.get())
        if not t_id:
            return

        teacher = self.project.teachers.get(t_id)

        # Show incharge sections if any
        incharge_secs = [s.display_name for s in self.project.sections.values() if s.class_teacher_id == t_id]
        if incharge_secs:
            tb.Label(
                self.grid_container,
                text=f"⭐ Class Incharge for: {', '.join(incharge_secs)}  |  Specialist: {self.project.subjects.get(teacher.primary_subject_id).name if teacher and teacher.primary_subject_id in self.project.subjects else 'General'}",
                font=("Helvetica", 10, "bold"),
                bootstyle="success"
            ).grid(row=0, column=0, columnspan=len(self.project.institution.working_days) + 1, sticky="w", pady=(0, 6))

        days = list(self.project.institution.working_days)
        periods_count = self.project.institution.get_max_periods_any_day()
        break_after = self.project.institution.break_after_period

        start_row = 1 if incharge_secs else 0

        # Header Row: Days by row, Periods by column!
        col_idx = 0
        tb.Label(self.grid_container, text="Day / Timing", font=("Helvetica", 9, "bold"), bootstyle="inverse-primary", padding=6).grid(row=start_row, column=col_idx, sticky="nsew", padx=1, pady=1)
        col_idx += 1

        for p in range(1, break_after + 1):
            time_lbl = self.project.institution.get_period_label(p)
            tb.Label(self.grid_container, text=time_lbl, font=("Helvetica", 9, "bold"), bootstyle="inverse-primary", padding=6).grid(row=start_row, column=col_idx, sticky="nsew", padx=1, pady=1)
            col_idx += 1

        tb.Label(self.grid_container, text="RECESS\n11:00-11:30", font=("Helvetica", 8, "bold"), bootstyle="warning", padding=6).grid(row=start_row, column=col_idx, sticky="nsew", padx=1, pady=1)
        col_idx += 1

        for p in range(break_after + 1, periods_count + 1):
            time_lbl = self.project.institution.get_period_label(p)
            tb.Label(self.grid_container, text=time_lbl, font=("Helvetica", 9, "bold"), bootstyle="inverse-primary", padding=6).grid(row=start_row, column=col_idx, sticky="nsew", padx=1, pady=1)
            col_idx += 1

        total_cols = col_idx

        # Day Rows
        for r_idx, day in enumerate(days, start=start_row + 1):
            col = 0
            fri_lbl = "\n(4 Periods)" if day == "Friday" else ""
            tb.Label(self.grid_container, text=f"{day}{fri_lbl}", font=("Helvetica", 9, "bold"), bootstyle="secondary", padding=6).grid(row=r_idx, column=col, sticky="nsew", padx=1, pady=1)
            col += 1

            day_max_p = self.project.institution.get_periods_for_day(day)

            for p in range(1, break_after + 1):
                if teacher and not teacher.is_available(day, p):
                    tb.Label(self.grid_container, text="🚫 Blocked", font=("Helvetica", 8), bootstyle="danger-outline", padding=6).grid(row=r_idx, column=col, sticky="nsew", padx=1, pady=1)
                else:
                    slot = self.project.get_teacher_slot_at(day, p, t_id)
                    self._create_cell_card(self.grid_container, slot, r_idx, col, context="teacher")
                col += 1

            tb.Label(self.grid_container, text="☕ RECESS", font=("Helvetica", 8, "bold"), bootstyle="warning-outline", padding=4).grid(row=r_idx, column=col, sticky="nsew", padx=1, pady=1)
            col += 1

            for p in range(break_after + 1, periods_count + 1):
                if p > day_max_p:
                    tb.Label(self.grid_container, text="— Dismissal —", font=("Helvetica", 8, "italic"), bootstyle="secondary-outline", padding=6).grid(row=r_idx, column=col, sticky="nsew", padx=1, pady=1)
                elif teacher and not teacher.is_available(day, p):
                    tb.Label(self.grid_container, text="🚫 Blocked", font=("Helvetica", 8), bootstyle="danger-outline", padding=6).grid(row=r_idx, column=col, sticky="nsew", padx=1, pady=1)
                else:
                    slot = self.project.get_teacher_slot_at(day, p, t_id)
                    self._create_cell_card(self.grid_container, slot, r_idx, col, context="teacher")
                col += 1

        for c in range(total_cols):
            self.grid_container.columnconfigure(c, weight=1)

    # ------------------ 3. Room View ------------------ #
    def _render_room_view(self):
        r_id = self._parse_id(self.combo_filter.get())
        if not r_id:
            return

        days = list(self.project.institution.working_days)
        periods_count = self.project.institution.get_max_periods_any_day()
        break_after = self.project.institution.break_after_period

        tb.Label(self.grid_container, text="Period / Timing", font=("Helvetica", 9, "bold"), bootstyle="inverse-primary", padding=6).grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        for c_idx, day in enumerate(days, start=1):
            fri_lbl = f" ({self.project.institution.get_periods_for_day(day)}P)" if day == "Friday" else ""
            tb.Label(self.grid_container, text=f"{day}{fri_lbl}", font=("Helvetica", 9, "bold"), bootstyle="inverse-primary", padding=6).grid(row=0, column=c_idx, sticky="nsew", padx=1, pady=1)

        row_idx = 1
        for p in range(1, periods_count + 1):
            time_lbl = self.project.institution.get_period_label(p)
            tb.Label(self.grid_container, text=time_lbl, font=("Helvetica", 8, "bold"), bootstyle="secondary", padding=6).grid(row=row_idx, column=0, sticky="nsew", padx=1, pady=1)

            for c_idx, day in enumerate(days, start=1):
                day_max_p = self.project.institution.get_periods_for_day(day)
                if p > day_max_p:
                    tb.Label(self.grid_container, text="— Early Dismissal —", font=("Helvetica", 8, "italic"), bootstyle="secondary-outline", padding=6).grid(row=row_idx, column=c_idx, sticky="nsew", padx=1, pady=1)
                    continue

                slot = self.project.get_room_slot_at(day, p, r_id)
                self._create_cell_card(self.grid_container, slot, row_idx, c_idx, context="room")

            row_idx += 1

            if p == break_after and p < periods_count:
                tb.Label(self.grid_container, text="RECESS", font=("Helvetica", 8, "bold"), bootstyle="warning", padding=4).grid(row=row_idx, column=0, sticky="nsew", padx=1, pady=1)
                for c_idx in range(1, len(days) + 1):
                    tb.Label(self.grid_container, text="☕ Break", font=("Helvetica", 8, "italic"), bootstyle="warning-outline", padding=4).grid(row=row_idx, column=c_idx, sticky="nsew", padx=1, pady=1)
                row_idx += 1

        for c in range(len(days) + 1):
            self.grid_container.columnconfigure(c, weight=1)

    # ------------------ 4. Master Matrix View ------------------ #
    def _render_master_matrix_view(self):
        target_day = self.combo_filter.get()
        if not target_day:
            return

        periods_count = self.project.institution.get_periods_for_day(target_day)
        sections = list(self.project.sections.values())

        day_note = f" (Early Dismissal after Period {periods_count})" if periods_count < self.project.institution.periods_per_day else ""
        tb.Label(self.grid_container, text=f"Class / Section{day_note}", font=("Helvetica", 9, "bold"), bootstyle="inverse-primary", padding=6).grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        for p in range(1, periods_count + 1):
            p_lbl = f"Period {p}"
            tb.Label(self.grid_container, text=p_lbl, font=("Helvetica", 9, "bold"), bootstyle="inverse-primary", padding=6).grid(row=0, column=p, sticky="nsew", padx=1, pady=1)

        for r_idx, sec in enumerate(sections, start=1):
            tb.Label(self.grid_container, text=sec.display_name, font=("Helvetica", 8, "bold"), bootstyle="secondary", padding=6).grid(row=r_idx, column=0, sticky="nsew", padx=1, pady=1)

            for p in range(1, periods_count + 1):
                slot = self.project.get_slot_at(target_day, p, sec.id)
                self._create_cell_card(self.grid_container, slot, r_idx, p, context="master")

        for c in range(periods_count + 1):
            self.grid_container.columnconfigure(c, weight=1)

    # ------------------ 5. Master Faculty Matrix View ------------------ #
    def _render_master_faculty_matrix_view(self):
        target_day = self.combo_filter.get()
        if not target_day:
            return

        periods_count = self.project.institution.get_periods_for_day(target_day)
        teachers = list(self.project.teachers.values())

        day_note = f" (Early Dismissal after Period {periods_count})" if periods_count < self.project.institution.periods_per_day else ""
        tb.Label(self.grid_container, text=f"Faculty Member{day_note}", font=("Helvetica", 9, "bold"), bootstyle="inverse-success", padding=6).grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        for p in range(1, periods_count + 1):
            p_lbl = f"Period {p}"
            tb.Label(self.grid_container, text=p_lbl, font=("Helvetica", 9, "bold"), bootstyle="inverse-success", padding=6).grid(row=0, column=p, sticky="nsew", padx=1, pady=1)

        for r_idx, teacher in enumerate(teachers, start=1):
            sub_spec = self.project.subjects.get(teacher.primary_subject_id)
            spec_code = f" [{sub_spec.code}]" if sub_spec else ""
            tb.Label(self.grid_container, text=f"{teacher.name}{spec_code}", font=("Helvetica", 8, "bold"), bootstyle="secondary", padding=6).grid(row=r_idx, column=0, sticky="nsew", padx=1, pady=1)

            for p in range(1, periods_count + 1):
                if not teacher.is_available(target_day, p):
                    lbl = tb.Label(self.grid_container, text="[Blocked]", font=("Helvetica", 8), bootstyle="danger-outline", padding=6)
                    lbl.grid(row=r_idx, column=p, sticky="nsew", padx=1, pady=1)
                    continue

                slot = self.project.get_teacher_slot_at(target_day, p, teacher.id)
                if slot:
                    self._create_cell_card(self.grid_container, slot, r_idx, p, context="master_faculty")
                else:
                    duty = self.project.get_teacher_duty_at(target_day, p, teacher.id)
                    if duty:
                        lbl = tb.Label(self.grid_container, text=f"🛡️ {duty.duty_name}", font=("Helvetica", 8, "bold"), bootstyle="warning", padding=6)
                        lbl.grid(row=r_idx, column=p, sticky="nsew", padx=1, pady=1)
                    else:
                        lbl = tb.Label(self.grid_container, text="Available", font=("Helvetica", 8), bootstyle="success-outline", padding=6)
                        lbl.grid(row=r_idx, column=p, sticky="nsew", padx=1, pady=1)

        for c in range(periods_count + 1):
            self.grid_container.columnconfigure(c, weight=1)

    # ------------------ Card Cell Helper ------------------ #
    def _create_cell_card(self, parent, slot: ScheduledSlot, row: int, col: int, context: str):
        if not slot:
            lbl = tb.Label(parent, text="— Free —", font=("Helvetica", 8), bootstyle="light", padding=6)
            lbl.grid(row=row, column=col, sticky="nsew", padx=1, pady=1)
            return

        sub = self.project.subjects.get(slot.subject_id)
        teacher = self.project.teachers.get(slot.teacher_id)
        sec = self.project.sections.get(slot.section_id)
        room = self.project.classrooms.get(slot.room_id)

        sub_name = sub.name if sub else slot.subject_id
        t_name = teacher.name if teacher else slot.teacher_id
        t_code = teacher.code if teacher else ""
        sec_name = sec.display_name if sec else slot.section_id
        r_name = room.name if room else ""
        is_locked = getattr(slot, 'is_locked', False)
        lock_badge = "🔒 " if is_locked else ""
        sync_badge = "🔬 Synced " if slot.sync_group_id else ""
        dur_badge = f"[{slot.duration}P] " if slot.duration > 1 else ""

        if context == "section":
            primary_txt = f"{lock_badge}{dur_badge}{sub_name}"
            secondary_txt = f"{t_name} • {r_name}"
        elif context == "teacher":
            primary_txt = f"{lock_badge}{dur_badge}{sec_name}"
            secondary_txt = f"{sub_name} • {r_name}"
        elif context == "room":
            primary_txt = f"{lock_badge}{dur_badge}{sec_name}"
            secondary_txt = f"{sub_name} • {t_code}"
        elif context == "master_faculty":
            primary_txt = f"{lock_badge}{sec_name}"
            secondary_txt = f"{sub.code if sub else sub_name} • {r_name}"
        else:  # Master matrix
            primary_txt = f"{lock_badge}{sub.code if sub else sub_name}"
            secondary_txt = f"{t_code} • {r_name}"

        card_style = "warning" if is_locked else ("info" if slot.sync_group_id else "secondary")
        card = tb.Frame(parent, bootstyle=card_style, padding=4)
        card.grid(row=row, column=col, sticky="nsew", padx=1, pady=1)

        lbl_p = tb.Label(
            card,
            text=primary_txt,
            font=("Helvetica", 8, "bold"),
            bootstyle="primary" if not slot.sync_group_id else "info"
        )
        lbl_p.pack(anchor=W)

        lbl_s = tb.Label(
            card,
            text=f"{sync_badge}{secondary_txt}",
            font=("Helvetica", 7),
            bootstyle="dark"
        )
        lbl_s.pack(anchor=W)

        # Click event to open edit slot dialog
        card.bind("<Button-1>", lambda e, s=slot: self._on_card_click(s))
        lbl_p.bind("<Button-1>", lambda e, s=slot: self._on_card_click(s))
        lbl_s.bind("<Button-1>", lambda e, s=slot: self._on_card_click(s))

    def _on_card_click(self, slot: ScheduledSlot):
        dlg = EditSlotDialog(self, self.project, slot, on_changed=self._render_grid)
        dlg.grab_set()

    # ------------------ Lock / Pin Management ------------------ #
    def _toggle_section_lock(self, section_id: str, lock_state: bool):
        sec_slots = self.project.get_section_slots(section_id)
        for s in sec_slots:
            s.is_locked = lock_state
        self._render_grid()
        status_word = "locked in place (pinned)" if lock_state else "unlocked"
        messagebox.showinfo("Section Locks Updated", f"All {len(sec_slots)} lectures for this section are now {status_word}!")

    def _lock_all_slots(self, lock_state: bool):
        if not self.project.schedule:
            messagebox.showwarning("Notice", "No timetable schedule generated yet to lock.")
            return
        for s in self.project.schedule:
            s.is_locked = lock_state
        self._render_grid()
        status_word = "locked in place (pinned)" if lock_state else "unlocked"
        messagebox.showinfo("Timetable Locks Updated", f"All {len(self.project.schedule)} lectures across the entire institution are now {status_word}!")

    # ------------------ Direct Solving Action ------------------ #
    def _on_generate_timetable(self):
        """Runs timetable solver directly from this view."""
        self.btn_gen_header.config(state="disabled", text="⏳ Solving...")

        def solve_worker():
            solver = TimetableSolver(self.project, timeout_seconds=30.0)
            res = solver.solve()

            duty_res = None
            if res.success and self.project.duty_slots:
                self.project.schedule = res.schedule
                duty_solver = DutyRosterSolver(self.project)
                duty_res = duty_solver.solve()
                if duty_res.success:
                    self.project.duty_assignments = duty_res.assignments

            self.after(0, lambda: self._on_solve_done(res, duty_res))

        threading.Thread(target=solve_worker, daemon=True).start()

    def _on_solve_done(self, res, duty_res=None):
        self.btn_gen_header.config(state="normal", text="⚡ Generate Timetable")

        if res.success:
            self.project.schedule = res.schedule
            self.project.is_generated = True
            import datetime
            self.project.last_generated_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.project.solve_stats = res.stats

            self.refresh()
            if self.on_update_callback:
                self.on_update_callback()

            messagebox.showinfo(
                "Timetable Generated!",
                f"{res.message}\n\nAll {len(res.schedule)} slots are now scheduled and visible below!"
            )
        else:
            messagebox.showerror("Solver Error", f"Could not solve timetable:\n\n{res.message}")

    def _on_load_sample_and_generate(self):
        new_proj = TimetableProject.create_sample_institution()
        self.project.institution = new_proj.institution
        self.project.classes = new_proj.classes
        self.project.sections = new_proj.sections
        self.project.subjects = new_proj.subjects
        self.project.teachers = new_proj.teachers
        self.project.classrooms = new_proj.classrooms
        self.project.lessons = new_proj.lessons
        self.project.duty_types = new_proj.duty_types
        self.project.duty_slots = new_proj.duty_slots
        self.project.clear_schedule()

        self._on_generate_timetable()

    def _on_quick_export(self):
        """Quick 1-click PDF export of current view."""
        if not self.project.is_generated or not self.project.schedule:
            messagebox.showwarning("Warning", "Generate timetable first before exporting.")
            return

        out_dir = os.path.abspath("exports_out")
        os.makedirs(out_dir, exist_ok=True)

        mode = self.combo_mode.get()
        pdf_gen = TimetablePDFGenerator(self.project)

        if mode == "Section / Class View":
            sec_id = self._parse_id(self.combo_filter.get())
            dest = os.path.join(out_dir, f"Class_Timetable_{sec_id}.pdf")
            pdf_gen.export_section_timetables_pdf(dest, target_section_id=sec_id)
        elif mode == "Faculty Teacher View":
            t_id = self._parse_id(self.combo_filter.get())
            dest = os.path.join(out_dir, f"Faculty_Timetable_{t_id}.pdf")
            pdf_gen.export_teacher_timetables_pdf(dest, target_teacher_id=t_id)
        else:
            dest = os.path.join(out_dir, "Master_Institutional_Matrix.pdf")
            pdf_gen.export_master_timetable_pdf(dest)

        if messagebox.askyesno("PDF Exported!", f"PDF saved:\n{dest}\n\nOpen document now?"):
            if os.name == 'nt':
                os.startfile(dest)

"""
Class & Section Curriculum Period Allotment View
Determines and configures class-wise and section-wise period quotas,
assigns qualified subject specialist teachers, monitors workload capacities,
and launches the constraint solver.
"""
import uuid
import threading
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox

from models.timetable_data import TimetableProject
from models.lesson import LessonAllocation
from solver.timetable_solver import TimetableSolver
from solver.duty_solver import DutyRosterSolver

class LessonsView(tb.Frame):
    def __init__(self, parent, project: TimetableProject, on_update_callback=None):
        super().__init__(parent)
        self.project = project
        self.on_update_callback = on_update_callback
        self.selected_lesson_id = None
        self.selected_section_id = None
        self.selected_teacher_id = None
        self.view_filter_mode = "section"  # "section" or "teacher"

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Header banner
        header = tb.Frame(self)
        header.pack(fill=X, padx=20, pady=(15, 10))

        tb.Label(
            header,
            text="Class & Teacher Curriculum Period Allotment",
            font=("Helvetica", 16, "bold"),
            bootstyle="primary"
        ).pack(side=LEFT)

        btn_box = tb.Frame(header)
        btn_box.pack(side=RIGHT)

        # BIG PROMINENT GENERATE BUTTON ON ALLOTMENT PAGE
        self.btn_gen = tb.Button(
            btn_box,
            text="⚡ GENERATE TIMETABLE",
            bootstyle="success",
            cursor="hand2",
            padding=(10, 6),
            command=self._on_generate_timetable
        )
        self.btn_gen.pack(side=LEFT, padx=(0, 8))

        tb.Button(
            btn_box,
            text="🔬 Aligned Practicals Wizard",
            bootstyle="info-outline",
            command=self._open_sync_wizard
        ).pack(side=LEFT)

        # Top Control & Mode Selector Bar
        selector_card = tb.Labelframe(self, text=" Filter & Workload Overview ", bootstyle="secondary", padding=12)
        selector_card.pack(fill=X, padx=20, pady=(0, 10))

        sec_row = tb.Frame(selector_card)
        sec_row.pack(fill=X)

        # View mode selector (aSc Timetables style: View by Class or View by Teacher)
        mode_frame = tb.Frame(sec_row)
        mode_frame.pack(side=LEFT, padx=(0, 15))

        self.var_mode = tb.StringVar(value="section")
        tb.Radiobutton(mode_frame, text="🏫 By Class", value="section", variable=self.var_mode, command=self._on_mode_switched).pack(side=LEFT, padx=3)
        tb.Radiobutton(mode_frame, text="👨‍🏫 By Teacher", value="teacher", variable=self.var_mode, command=self._on_mode_switched).pack(side=LEFT, padx=3)

        self.lbl_filter = tb.Label(sec_row, text="Select Class / Section:", font=("Helvetica", 10, "bold"))
        self.lbl_filter.pack(side=LEFT, padx=(0, 8))

        self.combo_active_filter = tb.Combobox(sec_row, state="readonly", width=28)
        self.combo_active_filter.pack(side=LEFT, padx=(0, 15))
        self.combo_active_filter.bind("<<ComboboxSelected>>", self._on_filter_changed)

        # Live Workload Meter
        self.lbl_sec_load = tb.Label(
            sec_row,
            text="Workload: 0 / 35 Periods",
            font=("Helvetica", 10, "bold"),
            bootstyle="primary"
        )
        self.lbl_sec_load.pack(side=LEFT, padx=(0, 10))

        self.sec_progress = tb.Progressbar(sec_row, length=180, mode="determinate", bootstyle="success")
        self.sec_progress.pack(side=LEFT, fill=X, expand=True)

        # Main Layout: Left (Allotment Table) and Right (Subject Specialist Assignment Form)
        main_frame = tb.Frame(self)
        main_frame.pack(fill=BOTH, expand=True, padx=20, pady=(0, 10))
        main_frame.columnconfigure(0, weight=4)
        main_frame.columnconfigure(1, weight=3)

        # Left: Allotment Table
        tbl_frame = tb.Frame(main_frame)
        tbl_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        cols = ("col1", "col2", "col3", "periods", "block", "room", "sync")
        self.tree = tb.Treeview(tbl_frame, columns=cols, show="headings", height=12, bootstyle="primary")
        self.tree.heading("col1", text="Subject Title")
        self.tree.heading("col2", text="Type")
        self.tree.heading("col3", text="Assigned Faculty (Specialist)")
        self.tree.heading("periods", text="Periods/Wk")
        self.tree.heading("block", text="Block Size")
        self.tree.heading("room", text="Designated Facility")
        self.tree.heading("sync", text="Aligned Group")

        self.tree.column("col1", width=140, anchor=W)
        self.tree.column("col2", width=80, anchor=W)
        self.tree.column("col3", width=160, anchor=W)
        self.tree.column("periods", width=75, anchor=CENTER)
        self.tree.column("block", width=75, anchor=CENTER)
        self.tree.column("room", width=120, anchor=W)
        self.tree.column("sync", width=110, anchor=W)

        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        sb = tb.Scrollbar(tbl_frame, orient="vertical", command=self.tree.yview)
        sb.pack(side=RIGHT, fill=Y)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Right: Allotment Form Card
        form_card = tb.Labelframe(main_frame, text=" Allot Subject / Assign Teacher ", bootstyle="secondary", padding=15)
        form_card.grid(row=0, column=1, sticky="nsew")

        tb.Label(form_card, text="Target Class & Section:", font=("Helvetica", 9, "bold")).pack(anchor=W, pady=(0, 2))
        self.combo_form_sec = tb.Combobox(form_card, state="readonly")
        self.combo_form_sec.pack(fill=X, pady=(0, 8))
        self.combo_form_sec.bind("<<ComboboxSelected>>", self._on_form_sec_changed)

        tb.Label(form_card, text="Subject to Allot:", font=("Helvetica", 9, "bold")).pack(anchor=W, pady=(2, 2))
        self.combo_subject = tb.Combobox(form_card, state="readonly")
        self.combo_subject.pack(fill=X, pady=(0, 8))
        self.combo_subject.bind("<<ComboboxSelected>>", self._on_subject_selected_in_form)

        tb.Label(form_card, text="Assigned Faculty (Specialist prioritized):", font=("Helvetica", 9, "bold")).pack(anchor=W, pady=(2, 2))
        self.combo_teacher = tb.Combobox(form_card, state="readonly")
        self.combo_teacher.pack(fill=X, pady=(0, 4))
        self.combo_teacher.bind("<<ComboboxSelected>>", self._on_teacher_selected_in_form)

        # Teacher current workload feedback
        self.lbl_teacher_workload = tb.Label(
            form_card,
            text="Teacher Weekly Load: —",
            font=("Helvetica", 8, "italic"),
            bootstyle="secondary"
        )
        self.lbl_teacher_workload.pack(anchor=W, pady=(0, 8))

        tb.Label(form_card, text="Designated Classroom or Specialized Lab:").pack(anchor=W, pady=(2, 2))
        self.combo_room = tb.Combobox(form_card, state="readonly")
        self.combo_room.pack(fill=X, pady=(0, 8))

        # Periods & Block size
        num_row = tb.Frame(form_card)
        num_row.pack(fill=X, pady=(4, 8))
        num_row.columnconfigure(0, weight=1)
        num_row.columnconfigure(1, weight=1)

        f_p = tb.Frame(num_row)
        f_p.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        tb.Label(f_p, text="Periods/Wk:", font=("Helvetica", 9, "bold")).pack(anchor=W)
        self.spin_periods = tb.Spinbox(f_p, from_=1, to=15, width=6)
        self.spin_periods.pack(fill=X)

        f_b = tb.Frame(num_row)
        f_b.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        tb.Label(f_b, text="Block (1=Single, 2=Double):").pack(anchor=W)
        self.spin_block = tb.Spinbox(f_b, from_=1, to=3, width=6)
        self.spin_block.pack(fill=X)

        tb.Label(form_card, text="Synchronized Practical Alignment Tag (Optional):").pack(anchor=W, pady=(4, 2))
        self.entry_sync = tb.Entry(form_card)
        self.entry_sync.pack(fill=X, pady=(0, 15))

        # Action Buttons
        btn_box = tb.Frame(form_card)
        btn_box.pack(fill=X, pady=(10, 0))

        tb.Button(btn_box, text="➕ Allot / Assign", bootstyle="success", command=self._on_add).pack(side=LEFT, padx=2)
        tb.Button(btn_box, text="💾 Update", bootstyle="primary", command=self._on_update).pack(side=LEFT, padx=2)
        tb.Button(btn_box, text="🗑️ Remove", bootstyle="danger", command=self._on_delete).pack(side=LEFT, padx=2)
        tb.Button(btn_box, text="Clear", bootstyle="secondary-outline", command=self._clear_form).pack(side=RIGHT)

    def refresh(self):
        sec_items = [f"{s.display_name} [{s.id}]" for s in self.project.sections.values()]
        self.combo_form_sec['values'] = sec_items

        if not self.selected_section_id and self.project.sections:
            self.selected_section_id = next(iter(self.project.sections.keys()))

        if not self.selected_teacher_id and self.project.teachers:
            self.selected_teacher_id = next(iter(self.project.teachers.keys()))

        if self.selected_section_id and self.selected_section_id in self.project.sections:
            sec = self.project.sections[self.selected_section_id]
            self.combo_form_sec.set(f"{sec.display_name} [{sec.id}]")

        self.combo_subject['values'] = [f"{s.name} ({s.code}) [{s.id}]" for s in self.project.subjects.values()]
        self.combo_room['values'] = ["(Auto Room from Subject)"] + [f"{r.name} [{r.id}]" for r in self.project.classrooms.values()]

        self._refresh_filter_options()
        self._refresh_allotments_table()
        self._update_teacher_dropdown_for_subject()

    def _on_mode_switched(self):
        self.view_filter_mode = self.var_mode.get()
        if self.view_filter_mode == "section":
            self.lbl_filter.config(text="Select Class / Section:")
            self.tree.heading("col1", text="Subject Title")
            self.tree.heading("col2", text="Type")
            self.tree.heading("col3", text="Assigned Faculty (Specialist)")
        else:
            self.lbl_filter.config(text="Select Faculty to Inspect:")
            self.tree.heading("col1", text="Target Class & Section")
            self.tree.heading("col2", text="Subject Title")
            self.tree.heading("col3", text="Type")

        self._refresh_filter_options()
        self._refresh_allotments_table()

    def _refresh_filter_options(self):
        if self.view_filter_mode == "section":
            items = [f"{s.display_name} [{s.id}]" for s in self.project.sections.values()]
            self.combo_active_filter['values'] = items
            if self.selected_section_id and self.selected_section_id in self.project.sections:
                sec = self.project.sections[self.selected_section_id]
                self.combo_active_filter.set(f"{sec.display_name} [{sec.id}]")
            elif items:
                self.combo_active_filter.set(items[0])
                self.selected_section_id = self._resolve_section_id(items[0])
        else:
            items = [f"{t.name} ({t.code}) [{t.id}]" for t in self.project.teachers.values()]
            self.combo_active_filter['values'] = items
            if self.selected_teacher_id and self.selected_teacher_id in self.project.teachers:
                t = self.project.teachers[self.selected_teacher_id]
                self.combo_active_filter.set(f"{t.name} ({t.code}) [{t.id}]")
            elif items:
                self.combo_active_filter.set(items[0])
                self.selected_teacher_id = self._resolve_teacher_id(items[0])

    def _on_filter_changed(self, event):
        sel_text = self.combo_active_filter.get()
        if self.view_filter_mode == "section":
            sec_id = self._resolve_section_id(sel_text)
            if sec_id:
                self.selected_section_id = sec_id
                sec = self.project.sections.get(sec_id)
                if sec:
                    self.combo_form_sec.set(f"{sec.display_name} [{sec.id}]")
        else:
            t_id = self._resolve_teacher_id(sel_text)
            if t_id:
                self.selected_teacher_id = t_id
                teacher = self.project.teachers.get(t_id)
                if teacher:
                    prefix = "⭐ Specialist: " if teacher.primary_subject_id else ""
                    self.combo_teacher.set(f"{prefix}{teacher.name} ({teacher.code}) [{teacher.id}]")
                    self._update_teacher_workload_label(t_id)
                    if teacher.primary_subject_id and teacher.primary_subject_id in self.project.subjects:
                        s = self.project.subjects[teacher.primary_subject_id]
                        self.combo_subject.set(f"{s.name} ({s.code}) [{s.id}]")

        self.selected_lesson_id = None
        self._refresh_allotments_table()

    def _on_form_sec_changed(self, event):
        sec_id = self._resolve_section_id(self.combo_form_sec.get())
        if sec_id:
            self.selected_section_id = sec_id
            if self.view_filter_mode == "section":
                sec = self.project.sections.get(sec_id)
                if sec:
                    self.combo_active_filter.set(f"{sec.display_name} [{sec.id}]")
                self._refresh_allotments_table()

    def _refresh_allotments_table(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        if self.view_filter_mode == "section":
            if not self.selected_section_id:
                return

            lessons = self.project.get_section_lessons(self.selected_section_id)
            total_allotted = sum(l.periods_per_week for l in lessons)
            total_weekly_slots = self.project.institution.get_total_weekly_slots()
            fri_p = self.project.institution.get_periods_for_day("Friday")
            fri_note = f" (Fri: {fri_p}p)" if "Friday" in self.project.institution.working_days else ""
            free_slots = max(0, total_weekly_slots - total_allotted)
            pct = min(100, int((total_allotted / total_weekly_slots) * 100)) if total_weekly_slots > 0 else 0

            self.lbl_sec_load.config(
                text=f"Class Load: {total_allotted} / {total_weekly_slots} Periods{fri_note}  •  {free_slots} Free Slots",
                bootstyle="success" if total_allotted <= total_weekly_slots else "danger"
            )
            self.sec_progress['value'] = pct

            for l in lessons:
                sub = self.project.subjects.get(l.subject_id)
                teacher = self.project.teachers.get(l.teacher_id)
                room = self.project.classrooms.get(l.room_id)

                sub_name = f"{sub.name} ({sub.code})" if sub else l.subject_id
                sub_type = sub.subject_type if sub else "Theory"

                is_spec = (sub and teacher and teacher.teaches_subject(sub.id))
                spec_badge = " ⭐ Specialist" if is_spec else ""
                t_str = f"{teacher.name} ({teacher.code}){spec_badge}" if teacher else l.teacher_id

                r_name = room.name if room else (sub.default_room_type if sub else "Classroom")
                sync_lbl = l.sync_group_name or l.sync_group_id or "—"

                self.tree.insert(
                    "", "end", iid=l.id,
                    values=(sub_name, sub_type, t_str, l.periods_per_week, l.block_size, r_name, sync_lbl)
                )
        else:
            if not self.selected_teacher_id:
                return

            teacher = self.project.teachers.get(self.selected_teacher_id)
            lessons = self.project.get_teacher_lessons(self.selected_teacher_id)
            total_allotted = sum(l.periods_per_week for l in lessons)
            max_w = teacher.max_periods_per_week if teacher else 24
            remaining = max_w - total_allotted
            pct = min(100, int((total_allotted / max_w) * 100)) if max_w > 0 else 0

            status_txt = f"{remaining} remaining capacity" if remaining >= 0 else f"Exceeds max by {-remaining}p!"
            self.lbl_sec_load.config(
                text=f"Teacher Load: {total_allotted} / {max_w} Periods  •  {status_txt}",
                bootstyle="success" if total_allotted <= max_w else "danger"
            )
            self.sec_progress['value'] = pct

            for l in lessons:
                sec = self.project.sections.get(l.section_id)
                sub = self.project.subjects.get(l.subject_id)
                room = self.project.classrooms.get(l.room_id)

                sec_name = sec.display_name if sec else l.section_id
                sub_name = f"{sub.name} ({sub.code})" if sub else l.subject_id
                sub_type = sub.subject_type if sub else "Theory"

                r_name = room.name if room else (sub.default_room_type if sub else "Classroom")
                sync_lbl = l.sync_group_name or l.sync_group_id or "—"

                self.tree.insert(
                    "", "end", iid=l.id,
                    values=(sec_name, sub_name, sub_type, l.periods_per_week, l.block_size, r_name, sync_lbl)
                )

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        l_id = sel[0]
        self.selected_lesson_id = l_id
        l = self.project.lessons.get(l_id)
        if not l:
            return

        sec = self.project.sections.get(l.section_id)
        sub = self.project.subjects.get(l.subject_id)
        teacher = self.project.teachers.get(l.teacher_id)
        room = self.project.classrooms.get(l.room_id)

        if sec:
            self.combo_form_sec.set(f"{sec.display_name} [{sec.id}]")

        if sub:
            self.combo_subject.set(f"{sub.name} ({sub.code}) [{sub.id}]")
            self._update_teacher_dropdown_for_subject(sub.id)

        if teacher:
            is_spec = (sub and teacher.teaches_subject(sub.id))
            prefix = "⭐ Specialist: " if is_spec else ""
            self.combo_teacher.set(f"{prefix}{teacher.name} ({teacher.code}) [{teacher.id}]")
            self._update_teacher_workload_label(teacher.id)

        if room:
            self.combo_room.set(f"{room.name} [{room.id}]")
        else:
            self.combo_room.set("(Auto Room from Subject)")

        self.spin_periods.set(l.periods_per_week)
        self.spin_block.set(l.block_size)
        self.entry_sync.delete(0, "end")
        self.entry_sync.insert(0, l.sync_group_id)

    def _on_subject_selected_in_form(self, event):
        sub_id = self._resolve_subject_id(self.combo_subject.get())
        if sub_id:
            self._update_teacher_dropdown_for_subject(sub_id)
            sub = self.project.subjects.get(sub_id)
            if sub and sub.allowed_double_period:
                self.spin_block.set(2)
            else:
                self.spin_block.set(1)

    def _update_teacher_dropdown_for_subject(self, subject_id: str = None):
        if not subject_id:
            subject_id = self._resolve_subject_id(self.combo_subject.get())

        specialist_teachers = []
        other_teachers = []

        for t in self.project.teachers.values():
            if subject_id and t.teaches_subject(subject_id):
                specialist_teachers.append(f"⭐ Specialist: {t.name} ({t.code}) [{t.id}]")
            else:
                other_teachers.append(f"{t.name} ({t.code}) [{t.id}]")

        combined = specialist_teachers + other_teachers
        self.combo_teacher['values'] = combined
        if specialist_teachers:
            self.combo_teacher.set(specialist_teachers[0])
            first_t_id = self._resolve_teacher_id(specialist_teachers[0])
            self._update_teacher_workload_label(first_t_id)
        elif combined:
            self.combo_teacher.set(combined[0])
            first_t_id = self._resolve_teacher_id(combined[0])
            self._update_teacher_workload_label(first_t_id)

    def _on_teacher_selected_in_form(self, event):
        t_id = self._resolve_teacher_id(self.combo_teacher.get())
        if t_id:
            self._update_teacher_workload_label(t_id)
            teacher = self.project.teachers.get(t_id)
            # If subject not selected yet, auto-select teacher's specialist field!
            if teacher and teacher.primary_subject_id and teacher.primary_subject_id in self.project.subjects:
                cur_sub_id = self._resolve_subject_id(self.combo_subject.get())
                if not cur_sub_id:
                    s = self.project.subjects[teacher.primary_subject_id]
                    self.combo_subject.set(f"{s.name} ({s.code}) [{s.id}]")
                    if s.allowed_double_period:
                        self.spin_block.set(2)

    def _update_teacher_workload_label(self, teacher_id: str):
        teacher = self.project.teachers.get(teacher_id)
        if teacher:
            current_load = self.project.get_teacher_allocated_periods(teacher.id)
            max_w = teacher.max_periods_per_week
            status_color = "success" if current_load <= max_w else "danger"
            remaining = max_w - current_load
            rem_str = f"({remaining} remaining)" if remaining >= 0 else f"(Exceeds limit by {-remaining}!)"
            self.lbl_teacher_workload.config(
                text=f"Teacher Load: {teacher.name} has {current_load} / {max_w} periods {rem_str}.",
                bootstyle=status_color
            )

    def _clear_form(self):
        self.selected_lesson_id = None
        self.spin_periods.set(4)
        self.spin_block.set(1)
        self.entry_sync.delete(0, "end")
        self.lbl_teacher_workload.config(text="Teacher Weekly Load: —", bootstyle="secondary")
        self.tree.selection_remove(self.tree.selection())

    def _parse_id(self, text: str) -> str:
        if "[" in text and text.endswith("]"):
            return text.split("[")[-1].rstrip("]")
        return ""

    def _resolve_teacher_id(self, text: str) -> str:
        t_id = self._parse_id(text)
        if t_id and t_id in self.project.teachers:
            return t_id
        clean = text.replace("⭐ Specialist:", "").replace("⭐", "").strip()
        for t in self.project.teachers.values():
            if t.id == clean or t.name == clean or t.code == clean or f"{t.name} ({t.code})" in clean:
                return t.id
        return ""

    def _resolve_subject_id(self, text: str) -> str:
        sub_id = self._parse_id(text)
        if sub_id and sub_id in self.project.subjects:
            return sub_id
        clean = text.strip()
        for s in self.project.subjects.values():
            if s.id == clean or s.name == clean or s.code == clean or f"{s.name} ({s.code})" in clean:
                return s.id
        return ""

    def _resolve_section_id(self, text: str) -> str:
        sec_id = self._parse_id(text)
        if sec_id and sec_id in self.project.sections:
            return sec_id
        clean = text.strip()
        for sec in self.project.sections.values():
            if sec.id == clean or sec.display_name == clean or sec.name == clean:
                return sec.id
        return ""

    def _on_add(self):
        target_sec_id = self._resolve_section_id(self.combo_form_sec.get()) or self.selected_section_id
        if not target_sec_id:
            messagebox.showerror("Error", "Please select a Target Class & Section.")
            return

        sub_id = self._resolve_subject_id(self.combo_subject.get())
        t_id = self._resolve_teacher_id(self.combo_teacher.get())
        r_id = self._parse_id(self.combo_room.get())

        if not sub_id or not t_id:
            messagebox.showerror("Error", "Subject and Faculty Instructor are required.")
            return

        l_id = f"L_{uuid.uuid4().hex[:6]}"
        l = LessonAllocation(
            id=l_id,
            section_id=target_sec_id,
            subject_id=sub_id,
            teacher_id=t_id,
            room_id=r_id,
            periods_per_week=int(self.spin_periods.get() or 4),
            block_size=int(self.spin_block.get() or 1),
            sync_group_id=self.entry_sync.get().strip()
        )
        self.project.lessons[l_id] = l
        self.selected_lesson_id = l_id
        self._refresh_allotments_table()
        self._update_teacher_workload_label(t_id)

        if self.on_update_callback:
            self.on_update_callback()

        sec = self.project.sections.get(target_sec_id)
        sub = self.project.subjects.get(sub_id)
        teacher = self.project.teachers.get(t_id)
        messagebox.showinfo("Assigned", f"Allotted {l.periods_per_week} periods of {sub.name if sub else 'Subject'} with {teacher.name if teacher else 'Teacher'} to {sec.display_name if sec else 'Section'}!")

    def _on_update(self):
        if not self.selected_lesson_id or self.selected_lesson_id not in self.project.lessons:
            messagebox.showwarning("Warning", "Select an allotted subject row to update.")
            return

        target_sec_id = self._resolve_section_id(self.combo_form_sec.get()) or self.selected_section_id
        sub_id = self._resolve_subject_id(self.combo_subject.get())
        t_id = self._resolve_teacher_id(self.combo_teacher.get())
        r_id = self._parse_id(self.combo_room.get())

        if not target_sec_id or not sub_id or not t_id:
            messagebox.showerror("Error", "Section, Subject and Teacher are required.")
            return

        l = self.project.lessons[self.selected_lesson_id]
        l.section_id = target_sec_id
        l.subject_id = sub_id
        l.teacher_id = t_id
        l.room_id = r_id
        l.periods_per_week = int(self.spin_periods.get() or 4)
        l.block_size = int(self.spin_block.get() or 1)
        l.sync_group_id = self.entry_sync.get().strip()

        self._refresh_allotments_table()
        self._update_teacher_workload_label(t_id)

        if self.on_update_callback:
            self.on_update_callback()

        messagebox.showinfo("Updated", "Curriculum allocation updated successfully!")

    def _on_delete(self):
        if not self.selected_lesson_id:
            return
        if messagebox.askyesno("Remove Allotment", "Remove this subject allotment?"):
            del self.project.lessons[self.selected_lesson_id]
            self.selected_lesson_id = None
            self._clear_form()
            self._refresh_allotments_table()
            if self.on_update_callback:
                self.on_update_callback()

    def _open_sync_wizard(self):
        from ui.dialogs.sync_group_dialog import SyncGroupWizardDialog
        dlg = SyncGroupWizardDialog(self, self.project, on_applied=self._refresh_section_allotments)
        dlg.grab_set()

    def _on_generate_timetable(self):
        """Runs the solver directly from the allotment screen!"""
        self.btn_gen.config(state="disabled", text="⏳ Solving...")

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
        self.btn_gen.config(state="normal", text="⚡ GENERATE TIMETABLE")

        if res.success:
            self.project.schedule = res.schedule
            self.project.is_generated = True
            import datetime
            self.project.last_generated_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.project.solve_stats = res.stats

            if self.on_update_callback:
                self.on_update_callback()

            extra = f"\n\nDuty Roster: {duty_res.message}" if duty_res else ""
            messagebox.showinfo(
                "Timetable Generated Successfully!",
                f"{res.message}{extra}\n\nSwitch to the 'Interactive Timetable' tab to see the color-coded schedule!"
            )
        else:
            messagebox.showerror("Solver Error", f"Could not solve timetable:\n\n{res.message}")

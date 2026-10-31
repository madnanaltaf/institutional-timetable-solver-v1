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

        self.var_all_sections = tb.BooleanVar(value=False)
        self.chk_all_sections = tb.Checkbutton(
            form_card,
            text="👥 Combined session — every section of this class at the same time",
            variable=self.var_all_sections,
            bootstyle="success-round-toggle"
        )
        self.chk_all_sections.pack(anchor=W, pady=(6, 4))

        align_hdr = tb.Frame(form_card)
        align_hdr.pack(fill=X, pady=(4, 2))
        tb.Label(
            align_hdr,
            text="🔗 Align at the same time with (Ctrl+Click to multi-select):",
            font=("Helvetica", 9, "bold")
        ).pack(side=LEFT)
        tb.Button(
            align_hdr,
            text="✂️ Clear Alignment",
            bootstyle="secondary-outline",
            padding=(4, 0),
            command=self._on_clear_alignment
        ).pack(side=RIGHT)

        align_cols = ("section", "subject", "teacher", "group")
        self.tree_align = tb.Treeview(form_card, columns=align_cols, show="headings", height=4, selectmode="extended", bootstyle="info")
        self.tree_align.heading("section", text="Class / Section")
        self.tree_align.heading("subject", text="Subject")
        self.tree_align.heading("teacher", text="Faculty")
        self.tree_align.heading("group", text="Aligned Group")
        self.tree_align.column("section", width=110, anchor=W)
        self.tree_align.column("subject", width=90, anchor=W)
        self.tree_align.column("teacher", width=90, anchor=W)
        self.tree_align.column("group", width=90, anchor=W)
        self.tree_align.pack(fill=X, pady=(0, 8))

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
        self._refresh_align_tree()
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
            self._refresh_align_tree()

    def _alignment_label(self, lesson: LessonAllocation) -> str:
        if lesson.combined_group_id:
            return "👥 All Sections"
        return lesson.sync_group_name or lesson.sync_group_id or "—"

    def _refresh_align_tree(self):
        """Lists allocations from other sections that a lesson can be aligned with."""
        for iid in self.tree_align.get_children():
            self.tree_align.delete(iid)

        target_sec_id = self._resolve_section_id(self.combo_form_sec.get()) or self.selected_section_id
        for l in self.project.lessons.values():
            if l.combined_group_id or l.section_id == target_sec_id:
                continue
            sec = self.project.sections.get(l.section_id)
            sub = self.project.subjects.get(l.subject_id)
            teacher = self.project.teachers.get(l.teacher_id)
            self.tree_align.insert(
                "", "end", iid=l.id,
                values=(
                    sec.display_name if sec else l.section_id,
                    sub.name if sub else l.subject_id,
                    teacher.name if teacher else l.teacher_id,
                    self._alignment_label(l)
                )
            )

    def _get_selected_align_ids(self) -> list:
        return list(self.tree_align.selection())

    def _select_alignment_peers(self, lesson: LessonAllocation):
        self.tree_align.selection_remove(self.tree_align.selection())
        group_id = lesson.combined_group_id or lesson.sync_group_id
        if not group_id:
            return
        for peer in self.project.lessons.values():
            if peer.id == lesson.id:
                continue
            if (lesson.combined_group_id and peer.combined_group_id == group_id) or (
                lesson.sync_group_id and peer.sync_group_id == group_id
            ):
                if self.tree_align.exists(peer.id):
                    self.tree_align.selection_add(peer.id)

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
                sync_lbl = self._alignment_label(l)

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
                sync_lbl = self._alignment_label(l)

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
            self.combo_teacher.set(f"{teacher.name} ({teacher.code}) [{teacher.id}]")
            self._update_teacher_workload_label(teacher.id)

        if room:
            self.combo_room.set(f"{room.name} [{room.id}]")
        else:
            self.combo_room.set("(Auto Room from Subject)")

        self.spin_periods.set(l.periods_per_week)
        self.spin_block.set(l.block_size)
        self.var_all_sections.set(bool(l.combined_group_id))
        self._select_alignment_peers(l)

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

        if subject_id:
            # Strictly show ONLY teachers who specialize in this subject!
            specialist_teachers = [
                f"{t.name} ({t.code}) [{t.id}]"
                for t in self.project.teachers.values()
                if t.teaches_subject(subject_id)
            ]
            if specialist_teachers:
                self.combo_teacher['values'] = specialist_teachers
                cur_t_id = self._resolve_teacher_id(self.combo_teacher.get())
                cur_t = self.project.teachers.get(cur_t_id)
                # Keep current selection if valid for this subject, otherwise default to first specialist
                if not cur_t or not cur_t.teaches_subject(subject_id):
                    self.combo_teacher.set(specialist_teachers[0])
                    first_t_id = self._resolve_teacher_id(specialist_teachers[0])
                    self._update_teacher_workload_label(first_t_id)
                else:
                    self._update_teacher_workload_label(cur_t_id)
            else:
                sub = self.project.subjects.get(subject_id)
                sub_label = sub.name if sub else subject_id
                self.combo_teacher['values'] = [f"(No specialist registered for {sub_label})"]
                self.combo_teacher.set(f"(No specialist registered for {sub_label})")
                self.lbl_teacher_workload.config(
                    text=f"⚠️ No specialist faculty registered for {sub_label}.",
                    bootstyle="warning"
                )
        else:
            all_teachers = [f"{t.name} ({t.code}) [{t.id}]" for t in self.project.teachers.values()]
            self.combo_teacher['values'] = all_teachers
            if all_teachers and not self.combo_teacher.get():
                self.combo_teacher.set(all_teachers[0])
                first_t_id = self._resolve_teacher_id(all_teachers[0])
                self._update_teacher_workload_label(first_t_id)

    def _on_teacher_selected_in_form(self, event):
        t_id = self._resolve_teacher_id(self.combo_teacher.get())
        if t_id:
            self._update_teacher_workload_label(t_id)
            teacher = self.project.teachers.get(t_id)
            # Synchronize subject to teacher's single specialized field
            if teacher and teacher.primary_subject_id and teacher.primary_subject_id in self.project.subjects:
                s = self.project.subjects[teacher.primary_subject_id]
                self.combo_subject.set(f"{s.name} ({s.code}) [{s.id}]")
                if s.allowed_double_period:
                    self.spin_block.set(2)
                else:
                    self.spin_block.set(1)

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
        self.var_all_sections.set(False)
        self.tree_align.selection_remove(self.tree_align.selection())
        self.lbl_teacher_workload.config(text="Teacher Weekly Load: —", bootstyle="secondary")
        self.tree.selection_remove(self.tree.selection())

    def _parse_id(self, text: str) -> str:
        if "[" in text and "]" in text:
            return text.split("[")[-1].split("]")[0].strip()
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

    def _read_form_values(self):
        return (
            self._resolve_section_id(self.combo_form_sec.get()) or self.selected_section_id,
            self._resolve_subject_id(self.combo_subject.get()),
            self._resolve_teacher_id(self.combo_teacher.get()),
            self._parse_id(self.combo_room.get()),
            int(self.spin_periods.get() or 4),
            int(self.spin_block.get() or 1),
        )

    def _validate_alignment(self, align_ids, target_sec_id, teacher_id, block_size, room_id):
        selected = [self.project.lessons[lid] for lid in align_ids if lid in self.project.lessons]
        if not selected:
            return "Select at least one existing allocation to align with."
        if any(l.section_id == target_sec_id for l in selected):
            return "Two lessons of the same section cannot be aligned at the same time."
        if any(l.combined_group_id for l in selected):
            return "Combined all-sections rows are aligned automatically — untick 'Combined session' to align manually."
        if any(l.block_size != block_size for l in selected):
            return "Aligned lessons must use the same block size."
        if any(l.teacher_id == teacher_id for l in selected):
            return "The same teacher cannot teach two aligned lessons at the same time."
        rooms = [l.room_id for l in selected if l.room_id]
        if room_id and room_id in rooms:
            return "Two aligned lessons would occupy the same room at the same time."
        if len(rooms) != len(set(rooms)):
            return "Two of the selected lessons already share the same room — they cannot be aligned."
        return ""

    def _apply_alignment(self, align_ids, target_sec_id, teacher_id, block_size, room_id):
        """Links the selected lessons into one simultaneous group. Returns (group_id, name)."""
        err = self._validate_alignment(align_ids, target_sec_id, teacher_id, block_size, room_id)
        if err:
            messagebox.showerror("Alignment Error", err)
            return None

        lessons = [self.project.lessons[lid] for lid in align_ids if lid in self.project.lessons]
        group_ids = {l.sync_group_id for l in lessons if l.sync_group_id}
        if len(group_ids) == 1:
            group_id = next(iter(group_ids))
            group_name = next((l.sync_group_name for l in lessons if l.sync_group_name), "")
        else:
            group_id = f"SYNC_ALIGN_{uuid.uuid4().hex[:6]}"
            group_name = "Custom Aligned Group"

        for l in lessons:
            l.sync_group_id = group_id
            l.sync_group_name = group_name
            l.combined_group_id = ""
            l.all_sections = False
        return group_id, group_name

    def _create_combined_session(self, target_sec_id, sub_id, t_id, r_id, periods, block):
        sec = self.project.sections.get(target_sec_id)
        if not sec:
            return []
        class_secs = self.project.get_class_sections(sec.class_id)
        if len(class_secs) < 2:
            messagebox.showwarning("Single-Section Class", "This class has only one section, so a normal allocation is created instead.")
            l = LessonAllocation(
                id=f"L_{uuid.uuid4().hex[:6]}", section_id=target_sec_id,
                subject_id=sub_id, teacher_id=t_id, room_id=r_id,
                periods_per_week=periods, block_size=block
            )
            self.project.lessons[l.id] = l
            return [l.id]

        group_id = f"COMBINED_{uuid.uuid4().hex[:8]}"
        created = []
        for cs in class_secs:
            l = LessonAllocation(
                id=f"L_{uuid.uuid4().hex[:6]}",
                section_id=cs.id,
                subject_id=sub_id,
                teacher_id=t_id,
                room_id=r_id,
                periods_per_week=periods,
                block_size=block,
                combined_group_id=group_id,
                all_sections=True
            )
            self.project.lessons[l.id] = l
            created.append(l.id)
        return created

    def _save_combined_session(self, lesson, target_sec_id, sub_id, t_id, r_id, periods, block):
        sec = self.project.sections.get(target_sec_id)
        if not sec:
            return
        class_secs = self.project.get_class_sections(sec.class_id)
        if len(class_secs) < 2:
            messagebox.showwarning("Single-Section Class", "This class has only one section; the combined session cannot be created.")
            return

        group_id = lesson.combined_group_id
        section_ids = {cs.id for cs in class_secs}
        existing = [x for x in self.project.lessons.values() if group_id and x.combined_group_id == group_id]

        if not group_id:
            # Converting a standalone row: rebuild all section rows from scratch.
            del self.project.lessons[lesson.id]
            existing = []
        elif any(x.section_id not in section_ids for x in existing):
            # The target class changed: drop the old group and rebuild.
            for x in existing:
                del self.project.lessons[x.id]
            existing = []
            group_id = ""

        if not group_id:
            group_id = f"COMBINED_{uuid.uuid4().hex[:8]}"
            existing = []

        by_section = {x.section_id: x for x in existing}
        for cs in class_secs:
            peer = by_section.get(cs.id)
            if peer is None:
                peer = LessonAllocation(
                    id=f"L_{uuid.uuid4().hex[:6]}",
                    section_id=cs.id,
                    subject_id=sub_id,
                    teacher_id=t_id,
                    room_id=r_id,
                    periods_per_week=periods,
                    block_size=block
                )
                self.project.lessons[peer.id] = peer
            peer.subject_id = sub_id
            peer.teacher_id = t_id
            peer.room_id = r_id
            peer.periods_per_week = periods
            peer.block_size = block
            peer.combined_group_id = group_id
            peer.all_sections = True
            peer.sync_group_id = ""
            peer.sync_group_name = ""
            if cs.id == target_sec_id:
                self.selected_lesson_id = peer.id

    def _dissolve_combined_group(self, lesson):
        """Unlinks a combined session, keeping the selected row and deleting its peers."""
        group_id = lesson.combined_group_id
        for x in list(self.project.lessons.values()):
            if x.combined_group_id and x.combined_group_id == group_id:
                if x.id == lesson.id:
                    x.combined_group_id = ""
                    x.all_sections = False
                else:
                    del self.project.lessons[x.id]

    def _on_add(self):
        target_sec_id, sub_id, t_id, r_id, periods, block = self._read_form_values()
        if not target_sec_id:
            messagebox.showerror("Error", "Please select a Target Class & Section.")
            return
        if not sub_id or not t_id:
            messagebox.showerror("Error", "Subject and Faculty Instructor are required.")
            return

        combined = bool(self.var_all_sections.get())
        align_ids = self._get_selected_align_ids()
        if combined and align_ids:
            messagebox.showerror("Choose One", "Use either a combined all-sections session or a manual alignment, not both.")
            return

        if combined:
            created = self._create_combined_session(target_sec_id, sub_id, t_id, r_id, periods, block)
            if not created:
                return
            self.selected_lesson_id = created[0]
            detail = f"all {len(created)} sections of the class"
        else:
            sync_gid, sync_name = "", ""
            if align_ids:
                group = self._apply_alignment(align_ids, target_sec_id, t_id, block, r_id)
                if group is None:
                    return
                sync_gid, sync_name = group

            l_id = f"L_{uuid.uuid4().hex[:6]}"
            self.project.lessons[l_id] = LessonAllocation(
                id=l_id,
                section_id=target_sec_id,
                subject_id=sub_id,
                teacher_id=t_id,
                room_id=r_id,
                periods_per_week=periods,
                block_size=block,
                sync_group_id=sync_gid,
                sync_group_name=sync_name
            )
            self.selected_lesson_id = l_id
            detail = "the selected section"

        self._refresh_allotments_table()
        self._refresh_align_tree()
        self._update_teacher_workload_label(t_id)

        if self.on_update_callback:
            self.on_update_callback()

        sec = self.project.sections.get(target_sec_id)
        sub = self.project.subjects.get(sub_id)
        teacher = self.project.teachers.get(t_id)
        messagebox.showinfo(
            "Assigned",
            f"Allotted {periods} periods of {sub.name if sub else 'Subject'} with "
            f"{teacher.name if teacher else 'Teacher'} to {sec.display_name if sec else 'Section'} "
            f"({detail})!"
        )

    def _on_update(self):
        if not self.selected_lesson_id or self.selected_lesson_id not in self.project.lessons:
            messagebox.showwarning("Warning", "Select an allotted subject row to update.")
            return

        target_sec_id, sub_id, t_id, r_id, periods, block = self._read_form_values()
        if not target_sec_id or not sub_id or not t_id:
            messagebox.showerror("Error", "Section, Subject and Teacher are required.")
            return

        l = self.project.lessons[self.selected_lesson_id]
        combined = bool(self.var_all_sections.get())
        align_ids = self._get_selected_align_ids()
        if combined and align_ids:
            messagebox.showerror("Choose One", "Use either a combined all-sections session or a manual alignment, not both.")
            return

        if combined:
            self._save_combined_session(l, target_sec_id, sub_id, t_id, r_id, periods, block)
        else:
            if l.combined_group_id:
                if not messagebox.askyesno(
                    "Break Combined Session",
                    "This removes the combined all-sections session and deletes the other sections' rows. Continue?"
                ):
                    return
                self._dissolve_combined_group(l)

            l.section_id = target_sec_id
            l.subject_id = sub_id
            l.teacher_id = t_id
            l.room_id = r_id
            l.periods_per_week = periods
            l.block_size = block
            l.combined_group_id = ""
            l.all_sections = False

            if align_ids:
                group = self._apply_alignment(align_ids, target_sec_id, t_id, block, r_id)
                if group is None:
                    return
                l.sync_group_id, l.sync_group_name = group
            elif not l.sync_group_id:
                l.sync_group_name = ""

        self._refresh_allotments_table()
        self._refresh_align_tree()
        self._update_teacher_workload_label(t_id)

        if self.on_update_callback:
            self.on_update_callback()

        messagebox.showinfo("Updated", "Curriculum allocation updated successfully!")

    def _on_delete(self):
        if not self.selected_lesson_id:
            return
        lesson = self.project.lessons.get(self.selected_lesson_id)
        if not lesson:
            return

        if lesson.combined_group_id:
            group = [l for l in self.project.lessons.values() if l.combined_group_id == lesson.combined_group_id]
            if not messagebox.askyesno("Remove Combined Session", f"Remove this combined session from all {len(group)} sections?"):
                return
            for l in group:
                self.project.lessons.pop(l.id, None)
        else:
            if not messagebox.askyesno("Remove Allotment", "Remove this subject allotment?"):
                return
            del self.project.lessons[self.selected_lesson_id]

        self.selected_lesson_id = None
        self._clear_form()
        self._refresh_allotments_table()
        self._refresh_align_tree()
        if self.on_update_callback:
            self.on_update_callback()

    def _on_clear_alignment(self):
        lesson = self.project.lessons.get(self.selected_lesson_id)
        if not lesson:
            messagebox.showwarning("Warning", "Select an allotted subject row first.")
            return
        if lesson.combined_group_id:
            if not messagebox.askyesno("Clear Combined Session", "Break this combined session? The other sections' rows will be removed."):
                return
            self._dissolve_combined_group(lesson)
        else:
            lesson.sync_group_id = ""
            lesson.sync_group_name = ""
        self.var_all_sections.set(False)
        self._refresh_allotments_table()
        self._refresh_align_tree()
        if self.on_update_callback:
            self.on_update_callback()

    def _open_sync_wizard(self):
        from ui.dialogs.sync_group_dialog import SyncGroupWizardDialog
        dlg = SyncGroupWizardDialog(self, self.project, on_applied=self.refresh)
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

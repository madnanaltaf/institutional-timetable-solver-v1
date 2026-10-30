"""
Teachers & Faculty View
Manages instructors, subject specializations, workloads, and an interactive availability matrix.
"""
import uuid
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox

from models.timetable_data import TimetableProject
from models.teacher import Teacher

class TeachersView(tb.Frame):
    def __init__(self, parent, project: TimetableProject, on_update_callback=None):
        super().__init__(parent)
        self.project = project
        self.on_update_callback = on_update_callback
        self.selected_teacher_id = None
        self.subject_check_vars = {}

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Header
        header = tb.Frame(self)
        header.pack(fill=X, padx=20, pady=(15, 10))
        tb.Label(header, text="Faculty Directory & Subject Specialist Profiles", font=("Helvetica", 16, "bold"), bootstyle="primary").pack(side=LEFT)

        # Content split: Left (Table & Form) and Right (Availability Grid)
        content = tb.Frame(self)
        content.pack(fill=BOTH, expand=True, padx=20, pady=10)
        content.columnconfigure(0, weight=4)
        content.columnconfigure(1, weight=3)

        # Left Column: List + Form
        left_col = tb.Frame(content)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # Teacher Table
        tbl_frame = tb.Frame(left_col)
        tbl_frame.pack(fill=BOTH, expand=True, pady=(0, 10))

        cols = ("code", "name", "specialist", "max_w", "max_d", "unavail")
        self.tree = tb.Treeview(tbl_frame, columns=cols, show="headings", height=8, bootstyle="primary")
        self.tree.heading("code", text="Code")
        self.tree.heading("name", text="Teacher Name")
        self.tree.heading("specialist", text="Subject Specializations")
        self.tree.heading("max_w", text="Max/Wk")
        self.tree.heading("max_d", text="Max/Day")
        self.tree.heading("unavail", text="Blocked Slots")

        self.tree.column("code", width=55, anchor=CENTER)
        self.tree.column("name", width=140, anchor=W)
        self.tree.column("specialist", width=180, anchor=W)
        self.tree.column("max_w", width=65, anchor=CENTER)
        self.tree.column("max_d", width=65, anchor=CENTER)
        self.tree.column("unavail", width=90, anchor=CENTER)

        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        sb = tb.Scrollbar(tbl_frame, orient="vertical", command=self.tree.yview)
        sb.pack(side=RIGHT, fill=Y)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Teacher Edit Form Card
        form_card = tb.Labelframe(left_col, text=" Teacher Details & Subject Specialization ", bootstyle="secondary", padding=10)
        form_card.pack(fill=X)

        f_r1 = tb.Frame(form_card)
        f_r1.pack(fill=X, pady=2)
        f_r1.columnconfigure(0, weight=1)
        f_r1.columnconfigure(1, weight=3)

        tb.Label(f_r1, text="Code:").grid(row=0, column=0, sticky=W)
        self.entry_code = tb.Entry(f_r1, width=8)
        self.entry_code.grid(row=0, column=0, sticky=E, padx=(45, 10))

        tb.Label(f_r1, text="Full Name:").grid(row=0, column=1, sticky=W)
        self.entry_name = tb.Entry(f_r1)
        self.entry_name.grid(row=0, column=1, sticky="ew", padx=(70, 0))

        f_r2 = tb.Frame(form_card)
        f_r2.pack(fill=X, pady=4)
        tb.Label(f_r2, text="Email:").pack(side=LEFT)
        self.entry_email = tb.Entry(f_r2)
        self.entry_email.pack(side=LEFT, fill=X, expand=True, padx=(10, 0))

        f_r3 = tb.Frame(form_card)
        f_r3.pack(fill=X, pady=4)
        tb.Label(f_r3, text="Max Periods/Week:").pack(side=LEFT)
        self.spin_max_w = tb.Spinbox(f_r3, from_=5, to=40, width=5)
        self.spin_max_w.pack(side=LEFT, padx=(5, 15))

        tb.Label(f_r3, text="Max Periods/Day:").pack(side=LEFT)
        self.spin_max_d = tb.Spinbox(f_r3, from_=1, to=8, width=5)
        self.spin_max_d.pack(side=LEFT, padx=(5, 0))

        # Single Subject Specialization Combobox (User Requirement: 1 Teacher = 1 Specialized Field)
        f_spec_single = tb.Frame(form_card)
        f_spec_single.pack(fill=X, pady=(6, 4))
        tb.Label(
            f_spec_single,
            text="⭐ Specialized Subject Field (Single Subject Specialist):",
            font=("Helvetica", 9, "bold"),
            bootstyle="primary"
        ).pack(anchor=W, pady=(0, 2))
        self.combo_primary_sub = tb.Combobox(f_spec_single, state="readonly")
        self.combo_primary_sub.pack(fill=X)
        self.combo_primary_sub.bind("<<ComboboxSelected>>", self._on_primary_subject_changed)

        # Subject Specialization Checklist Area
        spec_box = tb.Labelframe(form_card, text=" Additional Qualified Subject Specializations (Optional) ", bootstyle="info", padding=6)
        spec_box.pack(fill=X, pady=6)

        spec_btns_row = tb.Frame(spec_box)
        spec_btns_row.pack(fill=X, pady=(0, 4))
        tb.Button(spec_btns_row, text="Select All Subjects", bootstyle="info-outline", command=self._select_all_subjects).pack(side=LEFT, padx=(0, 4))
        tb.Button(spec_btns_row, text="Clear Subjects", bootstyle="secondary-outline", command=self._clear_all_subjects).pack(side=LEFT)

        self.spec_grid_container = tb.Frame(spec_box)
        self.spec_grid_container.pack(fill=X)

        # Buttons row
        btn_box = tb.Frame(form_card)
        btn_box.pack(fill=X, pady=(8, 0))

        tb.Button(btn_box, text="➕ Add New Teacher", bootstyle="success", command=self._on_add).pack(side=LEFT, padx=3)
        tb.Button(btn_box, text="💾 Update Selected", bootstyle="primary", command=self._on_update).pack(side=LEFT, padx=3)
        tb.Button(btn_box, text="🗑️ Delete", bootstyle="danger", command=self._on_delete).pack(side=LEFT, padx=3)
        tb.Button(btn_box, text="Clear Form", bootstyle="secondary-outline", command=self._clear_form).pack(side=RIGHT, padx=3)

        # Right Column: Interactive Availability Matrix
        right_col = tb.Frame(content)
        right_col.grid(row=0, column=1, sticky="nsew")

        self.matrix_card = tb.Labelframe(
            right_col,
            text=" Teacher Availability Matrix (Click cells to toggle Free / Unavailable) ",
            bootstyle="info",
            padding=10
        )
        self.matrix_card.pack(fill=BOTH, expand=True)

        self.lbl_selected_teacher = tb.Label(
            self.matrix_card,
            text="Select a teacher on the left to inspect and configure availability.",
            font=("Helvetica", 10, "bold"),
            bootstyle="secondary"
        )
        self.lbl_selected_teacher.pack(anchor=W, pady=(0, 8))

        # Quick action row for matrix (aSc Time-off fast buttons)
        mat_btn_row = tb.Frame(self.matrix_card)
        mat_btn_row.pack(fill=X, pady=(0, 8))

        tb.Button(mat_btn_row, text="✓ All Free", bootstyle="success-outline", command=self._on_mark_all_available).pack(side=LEFT, padx=3)
        tb.Button(mat_btn_row, text="🚫 Friday Dismissal", bootstyle="warning-outline", command=self._on_block_friday).pack(side=LEFT, padx=3)
        tb.Button(mat_btn_row, text="🚫 Block Period 1", bootstyle="secondary-outline", command=self._on_block_morning).pack(side=LEFT, padx=3)
        tb.Button(mat_btn_row, text="🚫 Block Late Period", bootstyle="secondary-outline", command=self._on_block_afternoon).pack(side=LEFT, padx=3)

        # Container for the grid of buttons
        self.grid_scroll_container = tb.Frame(self.matrix_card)
        self.grid_scroll_container.pack(fill=BOTH, expand=True)
        self.grid_cells = {}

    def _render_subject_checkboxes(self, qualified_ids=None):
        for w in self.spec_grid_container.winfo_children():
            w.destroy()

        self.subject_check_vars = {}
        if qualified_ids is None:
            qualified_ids = []

        subjects_list = list(self.project.subjects.values())
        if not subjects_list:
            tb.Label(self.spec_grid_container, text="No subjects created yet. Add subjects in Subjects tab.", font=("Helvetica", 8, "italic")).pack(anchor=W)
            return

        cols = 3
        for idx, sub in enumerate(subjects_list):
            r = idx // cols
            c = idx % cols
            var = tb.BooleanVar(value=(sub.id in qualified_ids))
            self.subject_check_vars[sub.id] = var

            chk = tb.Checkbutton(
                self.spec_grid_container,
                text=f"{sub.code} ({sub.name})",
                variable=var,
                bootstyle="round-toggle"
            )
            chk.grid(row=r, column=c, sticky=W, padx=4, pady=2)

    def _select_all_subjects(self):
        for var in self.subject_check_vars.values():
            var.set(True)

    def _clear_all_subjects(self):
        for var in self.subject_check_vars.values():
            var.set(False)

    def _parse_id(self, text: str) -> str:
        if "[" in text and text.endswith("]"):
            return text.split("[")[-1].rstrip("]")
        return ""

    def _on_primary_subject_changed(self, event):
        sub_id = self._parse_id(self.combo_primary_sub.get())
        if sub_id in self.subject_check_vars:
            self.subject_check_vars[sub_id].set(True)

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        sub_choices = ["(Select Single Subject Specialization)"] + [f"{s.name} ({s.code}) [{s.id}]" for s in self.project.subjects.values()]
        self.combo_primary_sub['values'] = sub_choices

        for t_id, t in self.project.teachers.items():
            # Get readable subject specialization labels
            prim_id = t.primary_subject_id or (t.qualified_subjects[0] if t.qualified_subjects else "")
            prim_sub = self.project.subjects.get(prim_id)
            spec_str = f"{prim_sub.name} ({prim_sub.code})" if prim_sub else "General Faculty"

            self.tree.insert(
                "", "end", iid=t_id,
                values=(t.code, t.name, spec_str, t.max_periods_per_week, t.max_periods_per_day, len(t.unavailable_slots))
            )

        if self.selected_teacher_id and self.selected_teacher_id in self.project.teachers:
            self.tree.selection_set(self.selected_teacher_id)
            teacher = self.project.teachers[self.selected_teacher_id]
            self._populate_form_from_teacher(teacher)
            self._render_availability_grid()
        elif self.project.teachers:
            first_id = next(iter(self.project.teachers.keys()))
            self.selected_teacher_id = first_id
            self.tree.selection_set(first_id)
            self._populate_form_from_teacher(self.project.teachers[first_id])
            self._render_availability_grid()
        else:
            self._render_subject_checkboxes([])

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        t_id = sel[0]
        self.selected_teacher_id = t_id
        teacher = self.project.teachers.get(t_id)
        if teacher:
            self._populate_form_from_teacher(teacher)
            self._render_availability_grid()

    def _populate_form_from_teacher(self, teacher: Teacher):
        self.entry_code.delete(0, "end")
        self.entry_code.insert(0, teacher.code)
        self.entry_name.delete(0, "end")
        self.entry_name.insert(0, teacher.name)
        self.entry_email.delete(0, "end")
        self.entry_email.insert(0, teacher.email)
        self.spin_max_w.set(teacher.max_periods_per_week)
        self.spin_max_d.set(teacher.max_periods_per_day)

        # Single subject specialty dropdown
        prim_id = teacher.primary_subject_id or (teacher.qualified_subjects[0] if teacher.qualified_subjects else "")
        if prim_id and prim_id in self.project.subjects:
            s = self.project.subjects[prim_id]
            self.combo_primary_sub.set(f"{s.name} ({s.code}) [{s.id}]")
        else:
            self.combo_primary_sub.set("(Select Single Subject Specialization)")

        # Check specializations
        self._render_subject_checkboxes(teacher.qualified_subjects)

    def _clear_form(self):
        self.selected_teacher_id = None
        self.entry_code.delete(0, "end")
        self.entry_name.delete(0, "end")
        self.entry_email.delete(0, "end")
        self.spin_max_w.set(24)
        self.spin_max_d.set(5)
        self.combo_primary_sub.set("(Select Single Subject Specialization)")
        self._clear_all_subjects()
        self.tree.selection_remove(self.tree.selection())
        self.lbl_selected_teacher.config(text="Select a faculty member from the list to view/edit availability matrix.")

    def _render_availability_grid(self):
        for widget in self.grid_scroll_container.winfo_children():
            widget.destroy()

        self.grid_cells = {}
        if not self.selected_teacher_id or self.selected_teacher_id not in self.project.teachers:
            return

        teacher = self.project.teachers[self.selected_teacher_id]
        self.lbl_selected_teacher.config(
            text=f"Availability for: {teacher.name} ({teacher.code}) — {len(teacher.unavailable_slots)} blocked slots"
        )

        days = list(self.project.institution.working_days)
        periods_count = self.project.institution.periods_per_day

        tb.Label(self.grid_scroll_container, text="Day / Period", font=("Helvetica", 9, "bold")).grid(row=0, column=0, padx=4, pady=4, sticky="nsew")
        for p in range(1, periods_count + 1):
            p_lbl = f"P{p}"
            tb.Label(self.grid_scroll_container, text=p_lbl, font=("Helvetica", 8, "bold")).grid(row=0, column=p, padx=2, pady=4, sticky="nsew")

        for r_idx, day in enumerate(days, start=1):
            tb.Label(self.grid_scroll_container, text=day, font=("Helvetica", 8, "bold")).grid(row=r_idx, column=0, padx=4, pady=2, sticky=W)
            for p in range(1, periods_count + 1):
                is_unavail = teacher.is_unavailable(day, p)
                btn_style = "danger" if is_unavail else "success-outline"
                btn_txt = "🚫 Busy" if is_unavail else "✓ Free"

                btn = tb.Button(
                    self.grid_scroll_container,
                    text=btn_txt,
                    bootstyle=btn_style,
                    width=7,
                    command=lambda d=day, p_num=p: self._toggle_cell_availability(d, p_num)
                )
                btn.grid(row=r_idx, column=p, padx=2, pady=2, sticky="nsew")
                self.grid_cells[(day, p)] = btn

        for c in range(periods_count + 1):
            self.grid_scroll_container.columnconfigure(c, weight=1)

    def _toggle_cell_availability(self, day: str, period: int):
        if not self.selected_teacher_id:
            return
        teacher = self.project.teachers[self.selected_teacher_id]
        if teacher.is_unavailable(day, period):
            teacher.remove_unavailable_slot(day, period)
        else:
            teacher.add_unavailable_slot(day, period)

        self._render_availability_grid()
        self._update_tree_row(teacher)
        if self.on_update_callback:
            self.on_update_callback()

    def _on_mark_all_available(self):
        if not self.selected_teacher_id:
            return
        teacher = self.project.teachers[self.selected_teacher_id]
        teacher.unavailable_slots.clear()
        self._render_availability_grid()
        self._update_tree_row(teacher)
        if self.on_update_callback:
            self.on_update_callback()

    def _on_block_friday(self):
        if not self.selected_teacher_id:
            return
        teacher = self.project.teachers[self.selected_teacher_id]
        fri_periods = self.project.institution.get_periods_for_day("Friday")
        for p in range(fri_periods + 1, self.project.institution.periods_per_day + 1):
            teacher.add_unavailable_slot("Friday", p)
        self._render_availability_grid()
        self._update_tree_row(teacher)
        if self.on_update_callback:
            self.on_update_callback()

    def _on_block_morning(self):
        if not self.selected_teacher_id:
            return
        teacher = self.project.teachers[self.selected_teacher_id]
        for day in self.project.institution.working_days:
            teacher.add_unavailable_slot(day, 1)
        self._render_availability_grid()
        self._update_tree_row(teacher)
        if self.on_update_callback:
            self.on_update_callback()

    def _on_block_afternoon(self):
        if not self.selected_teacher_id:
            return
        teacher = self.project.teachers[self.selected_teacher_id]
        for day in self.project.institution.working_days:
            day_p = self.project.institution.get_periods_for_day(day)
            teacher.add_unavailable_slot(day, day_p)
        self._render_availability_grid()
        self._update_tree_row(teacher)
        if self.on_update_callback:
            self.on_update_callback()

    def _auto_generate_teacher_code(self, name: str) -> str:
        parts = [p for p in name.replace(".", " ").replace(",", " ").split() if p]
        if len(parts) >= 2:
            base_code = (parts[0][0] + parts[-1][0]).upper()
        elif parts:
            base_code = parts[0][:3].upper()
        else:
            base_code = "TCH"

        code = base_code
        counter = 1
        existing_codes = {t.code for t in self.project.teachers.values()}
        while code in existing_codes:
            code = f"{base_code}{counter}"
            counter += 1
        return code

    def _update_tree_row(self, teacher: Teacher):
        if self.tree.exists(teacher.id):
            spec_names = [self.project.subjects[s_id].code for s_id in teacher.qualified_subjects if s_id in self.project.subjects]
            spec_str = ", ".join(spec_names) if spec_names else "General Faculty"
            self.tree.item(
                teacher.id,
                values=(teacher.code, teacher.name, spec_str, teacher.max_periods_per_week, teacher.max_periods_per_day, len(teacher.unavailable_slots))
            )

    def _on_add(self):
        name = self.entry_name.get().strip()
        code = self.entry_code.get().strip()
        if not name:
            messagebox.showerror("Error", "Teacher Name is required!")
            return

        if not code:
            code = self._auto_generate_teacher_code(name)
            self.entry_code.delete(0, "end")
            self.entry_code.insert(0, code)

        primary_sub_id = self._parse_id(self.combo_primary_sub.get())
        chosen_specs = [s_id for s_id, var in self.subject_check_vars.items() if var.get()]
        if primary_sub_id and primary_sub_id not in chosen_specs:
            chosen_specs.insert(0, primary_sub_id)
        elif not primary_sub_id and chosen_specs:
            primary_sub_id = chosen_specs[0]

        t_id = f"t_{uuid.uuid4().hex[:6]}"
        new_teacher = Teacher(
            id=t_id,
            name=name,
            code=code,
            email=self.entry_email.get().strip(),
            primary_subject_id=primary_sub_id,
            qualified_subjects=chosen_specs,
            max_periods_per_week=int(self.spin_max_w.get() or 24),
            max_periods_per_day=int(self.spin_max_d.get() or 5)
        )
        self.project.teachers[t_id] = new_teacher
        self.selected_teacher_id = t_id
        self.refresh()
        if self.on_update_callback:
            self.on_update_callback()

        sub_obj = self.project.subjects.get(primary_sub_id)
        sub_name = sub_obj.name if sub_obj else "General"
        messagebox.showinfo("Teacher Added", f"Teacher '{name}' ({code}) added successfully as specialist for {sub_name}!")

    def _on_update(self):
        if not self.selected_teacher_id or self.selected_teacher_id not in self.project.teachers:
            messagebox.showwarning("Warning", "Select a teacher to update.")
            return

        teacher = self.project.teachers[self.selected_teacher_id]
        name = self.entry_name.get().strip()
        code = self.entry_code.get().strip()
        if not name:
            messagebox.showerror("Error", "Teacher Name cannot be empty.")
            return

        if not code:
            code = self._auto_generate_teacher_code(name)
            self.entry_code.delete(0, "end")
            self.entry_code.insert(0, code)

        primary_sub_id = self._parse_id(self.combo_primary_sub.get())
        chosen_specs = [s_id for s_id, var in self.subject_check_vars.items() if var.get()]
        if primary_sub_id and primary_sub_id not in chosen_specs:
            chosen_specs.insert(0, primary_sub_id)
        elif not primary_sub_id and chosen_specs:
            primary_sub_id = chosen_specs[0]

        teacher.name = name
        teacher.code = code
        teacher.email = self.entry_email.get().strip()
        teacher.primary_subject_id = primary_sub_id
        teacher.qualified_subjects = chosen_specs
        teacher.max_periods_per_week = int(self.spin_max_w.get() or 24)
        teacher.max_periods_per_day = int(self.spin_max_d.get() or 5)

        self.refresh()
        if self.on_update_callback:
            self.on_update_callback()

        sub_obj = self.project.subjects.get(primary_sub_id)
        sub_name = sub_obj.name if sub_obj else "General"
        messagebox.showinfo("Updated", f"Updated '{teacher.name}' ({teacher.code}) as specialist for {sub_name}!")

    def _on_delete(self):
        if not self.selected_teacher_id:
            return
        if messagebox.askyesno("Delete Teacher", f"Remove teacher '{self.project.teachers[self.selected_teacher_id].name}'?"):
            del self.project.teachers[self.selected_teacher_id]
            self.selected_teacher_id = None
            self._clear_form()
            self.refresh()
            if self.on_update_callback:
                self.on_update_callback()

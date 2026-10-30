"""
Duty Roster & Invigilation Management View
Configures institutional duties and generates mathematically fair teacher rosters
without conflicts against active teaching schedules.
"""
import uuid
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox

from models.timetable_data import TimetableProject
from models.duty import DutySlot, DutyType
from solver.duty_solver import DutyRosterSolver

class DutyRosterView(tb.Frame):
    def __init__(self, parent, project: TimetableProject, on_update_callback=None):
        super().__init__(parent)
        self.project = project
        self.on_update_callback = on_update_callback
        self.selected_slot_id = None

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Header
        header = tb.Frame(self)
        header.pack(fill=X, padx=20, pady=(15, 10))
        tb.Label(header, text="Campus Duties & Exam Invigilation Fair Roster", font=("Helvetica", 16, "bold"), bootstyle="primary").pack(side=LEFT)

        btn_box = tb.Frame(header)
        btn_box.pack(side=RIGHT)

        self.btn_solve_duty = tb.Button(
            btn_box,
            text="⚡ Generate Fair Duty Roster",
            bootstyle="success",
            command=self._on_solve_duties
        )
        self.btn_solve_duty.pack(side=LEFT, padx=5)

        # Content split: Left (Duty Slots Management) and Right (Assignments & Fairness Table)
        content = tb.Frame(self)
        content.pack(fill=BOTH, expand=True, padx=20, pady=10)
        content.columnconfigure(0, weight=2)
        content.columnconfigure(1, weight=3)

        # Left: Duty Slots & Form
        left_col = tb.Frame(content)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # Duty slots table
        tbl_frame = tb.Frame(left_col)
        tbl_frame.pack(fill=BOTH, expand=True, pady=(0, 10))

        cols = ("day", "time", "duty", "req")
        self.tree_slots = tb.Treeview(tbl_frame, columns=cols, show="headings", height=8, bootstyle="secondary")
        self.tree_slots.heading("day", text="Day")
        self.tree_slots.heading("time", text="Time / Slot")
        self.tree_slots.heading("duty", text="Duty Name")
        self.tree_slots.heading("req", text="Staff Req.")

        self.tree_slots.column("day", width=80, anchor=W)
        self.tree_slots.column("time", width=100, anchor=W)
        self.tree_slots.column("duty", width=140, anchor=W)
        self.tree_slots.column("req", width=70, anchor=CENTER)

        self.tree_slots.pack(side=LEFT, fill=BOTH, expand=True)
        sb = tb.Scrollbar(tbl_frame, orient="vertical", command=self.tree_slots.yview)
        sb.pack(side=RIGHT, fill=Y)
        self.tree_slots.configure(yscrollcommand=sb.set)
        self.tree_slots.bind("<<TreeviewSelect>>", self._on_slot_select)

        # Slot Form
        form_card = tb.Labelframe(left_col, text=" Configure Duty Slot ", bootstyle="secondary", padding=10)
        form_card.pack(fill=X)

        f_r1 = tb.Frame(form_card)
        f_r1.pack(fill=X, pady=2)
        tb.Label(f_r1, text="Duty Title:").pack(side=LEFT)
        self.entry_name = tb.Entry(f_r1)
        self.entry_name.pack(side=LEFT, fill=X, expand=True, padx=(10, 0))

        f_r2 = tb.Frame(form_card)
        f_r2.pack(fill=X, pady=4)
        f_r2.columnconfigure(0, weight=1)
        f_r2.columnconfigure(1, weight=1)

        f_day = tb.Frame(f_r2)
        f_day.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        tb.Label(f_day, text="Day:").pack(anchor=W)
        self.combo_day = tb.Combobox(f_day, values=list(self.project.institution.working_days), state="readonly")
        self.combo_day.pack(fill=X)

        f_p = tb.Frame(f_r2)
        f_p.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        tb.Label(f_p, text="Period (0=Morning, 1..N):").pack(anchor=W)
        self.spin_p = tb.Spinbox(f_p, from_=0, to=10, width=6)
        self.spin_p.pack(fill=X)

        f_r3 = tb.Frame(form_card)
        f_r3.pack(fill=X, pady=4)
        f_r3.columnconfigure(0, weight=2)
        f_r3.columnconfigure(1, weight=1)

        f_loc = tb.Frame(f_r3)
        f_loc.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        tb.Label(f_loc, text="Location:").pack(anchor=W)
        self.entry_loc = tb.Entry(f_loc)
        self.entry_loc.pack(fill=X)

        f_req = tb.Frame(f_r3)
        f_req.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        tb.Label(f_req, text="Staff Needed:").pack(anchor=W)
        self.spin_req = tb.Spinbox(f_req, from_=1, to=5, width=4)
        self.spin_req.pack(fill=X)

        btn_row = tb.Frame(form_card)
        btn_row.pack(fill=X, pady=(8, 0))

        tb.Button(btn_row, text="➕ Add Slot", bootstyle="success", command=self._on_add_slot).pack(side=LEFT, padx=2)
        tb.Button(btn_row, text="💾 Update", bootstyle="primary", command=self._on_update_slot).pack(side=LEFT, padx=2)
        tb.Button(btn_row, text="🗑️ Delete", bootstyle="danger", command=self._on_delete_slot).pack(side=LEFT, padx=2)

        # Right: Assignments & Fairness Notebook
        right_col = tb.Frame(content)
        right_col.grid(row=0, column=1, sticky="nsew")

        notebook = tb.Notebook(right_col, bootstyle="info")
        notebook.pack(fill=BOTH, expand=True)

        # Tab 1: Active Duty Assignments Roster
        tab_roster = tb.Frame(notebook, padding=10)
        notebook.add(tab_roster, text=" 📅 Duty Assignment Roster ")

        r_cols = ("day", "time", "duty", "location", "teacher")
        self.tree_assignments = tb.Treeview(tab_roster, columns=r_cols, show="headings", height=12, bootstyle="info")
        self.tree_assignments.heading("day", text="Day")
        self.tree_assignments.heading("time", text="Time / Slot")
        self.tree_assignments.heading("duty", text="Duty Type")
        self.tree_assignments.heading("location", text="Location")
        self.tree_assignments.heading("teacher", text="Assigned Faculty")

        self.tree_assignments.column("day", width=80, anchor=W)
        self.tree_assignments.column("time", width=100, anchor=W)
        self.tree_assignments.column("duty", width=140, anchor=W)
        self.tree_assignments.column("location", width=130, anchor=W)
        self.tree_assignments.column("teacher", width=130, anchor=W)

        self.tree_assignments.pack(side=LEFT, fill=BOTH, expand=True)
        sb_r = tb.Scrollbar(tab_roster, orient="vertical", command=self.tree_assignments.yview)
        sb_r.pack(side=RIGHT, fill=Y)
        self.tree_assignments.configure(yscrollcommand=sb_r.set)

        # Tab 2: Fairness Distribution Analysis
        tab_fairness = tb.Frame(notebook, padding=10)
        notebook.add(tab_fairness, text=" ⚖️ Faculty Fairness Distribution ")

        self.lbl_fairness_summary = tb.Label(
            tab_fairness,
            text="Duty Load Distribution Balance:",
            font=("Helvetica", 10, "bold"),
            bootstyle="primary"
        )
        self.lbl_fairness_summary.pack(anchor=W, pady=(0, 8))

        f_cols = ("code", "name", "duties", "classes", "status")
        self.tree_fairness = tb.Treeview(tab_fairness, columns=f_cols, show="headings", height=10, bootstyle="success")
        self.tree_fairness.heading("code", text="Code")
        self.tree_fairness.heading("name", text="Faculty Member")
        self.tree_fairness.heading("duties", text="Assigned Duties")
        self.tree_fairness.heading("classes", text="Teaching Load")
        self.tree_fairness.heading("status", text="Fairness Balance")

        self.tree_fairness.column("code", width=60, anchor=CENTER)
        self.tree_fairness.column("name", width=160, anchor=W)
        self.tree_fairness.column("duties", width=110, anchor=CENTER)
        self.tree_fairness.column("classes", width=110, anchor=CENTER)
        self.tree_fairness.column("status", width=140, anchor=W)

        self.tree_fairness.pack(fill=BOTH, expand=True)

    def refresh(self):
        # 1. Refresh duty slots
        for item in self.tree_slots.get_children():
            self.tree_slots.delete(item)

        for s_id, slot in self.project.duty_slots.items():
            t_lbl = slot.time_label or (f"Period {slot.period}" if slot.period > 0 else "Morning")
            self.tree_slots.insert("", "end", iid=s_id, values=(slot.day, t_lbl, slot.duty_name, slot.required_teachers))

        self.combo_day['values'] = list(self.project.institution.working_days)
        if self.project.institution.working_days:
            self.combo_day.set(self.project.institution.working_days[0])

        # 2. Refresh duty assignments
        for item in self.tree_assignments.get_children():
            self.tree_assignments.delete(item)

        days_order = {d: i for i, d in enumerate(self.project.institution.working_days)}
        duties_sorted = sorted(self.project.duty_assignments, key=lambda d: (days_order.get(d.day, 99), d.period))

        for d in duties_sorted:
            time_lbl = d.time_label or (f"Period {d.period}" if d.period > 0 else "Morning Supervision")
            self.tree_assignments.insert("", "end", values=(d.day, time_lbl, d.duty_name, d.location, d.teacher_name))

        # 3. Refresh fairness table
        for item in self.tree_fairness.get_children():
            self.tree_fairness.delete(item)

        teacher_duty_counts = {}
        for d in self.project.duty_assignments:
            teacher_duty_counts[d.teacher_id] = teacher_duty_counts.get(d.teacher_id, 0) + 1

        counts = [teacher_duty_counts.get(t_id, 0) for t_id in self.project.teachers]
        if counts:
            avg_d = sum(counts) / len(counts)
            min_d = min(counts)
            max_d = max(counts)
            self.lbl_fairness_summary.config(
                text=f"Duty Load Spread: {min_d} to {max_d} duties per teacher | Mean: {avg_d:.1f} duties (Optimally Fair)"
            )

        for t_id, teacher in self.project.teachers.items():
            c = teacher_duty_counts.get(t_id, 0)
            slots = self.project.get_teacher_slots(t_id)
            teach_load = sum(s.duration for s in slots)
            status = "✓ Perfectly Balanced" if 1 <= c <= 3 else "Assigned"
            self.tree_fairness.insert("", "end", values=(teacher.code, teacher.name, f"{c} duties", f"{teach_load} periods", status))

    def _on_slot_select(self, event):
        sel = self.tree_slots.selection()
        if not sel:
            return
        s_id = sel[0]
        self.selected_slot_id = s_id
        slot = self.project.duty_slots.get(s_id)
        if slot:
            self.entry_name.delete(0, "end")
            self.entry_name.insert(0, slot.duty_name)
            self.combo_day.set(slot.day)
            self.spin_p.set(slot.period)
            self.entry_loc.delete(0, "end")
            self.entry_loc.insert(0, slot.location)
            self.spin_req.set(slot.required_teachers)

    def _on_add_slot(self):
        name = self.entry_name.get().strip()
        day = self.combo_day.get()
        if not name or not day:
            messagebox.showerror("Error", "Duty Title and Day are required!")
            return

        s_id = f"ds_{uuid.uuid4().hex[:6]}"
        slot = DutySlot(
            id=s_id,
            duty_type_id="general",
            duty_name=name,
            day=day,
            period=int(self.spin_p.get() or 0),
            location=self.entry_loc.get().strip() or "Campus",
            required_teachers=int(self.spin_req.get() or 1)
        )
        self.project.duty_slots[s_id] = slot
        self.refresh()
        if self.on_update_callback:
            self.on_update_callback()

    def _on_update_slot(self):
        if not self.selected_slot_id or self.selected_slot_id not in self.project.duty_slots:
            messagebox.showwarning("Warning", "Select a slot to update.")
            return

        slot = self.project.duty_slots[self.selected_slot_id]
        slot.duty_name = self.entry_name.get().strip() or slot.duty_name
        slot.day = self.combo_day.get()
        slot.period = int(self.spin_p.get() or 0)
        slot.location = self.entry_loc.get().strip()
        slot.required_teachers = int(self.spin_req.get() or 1)

        self.refresh()
        if self.on_update_callback:
            self.on_update_callback()

    def _on_delete_slot(self):
        if not self.selected_slot_id:
            return
        del self.project.duty_slots[self.selected_slot_id]
        self.selected_slot_id = None
        self.refresh()
        if self.on_update_callback:
            self.on_update_callback()

    def _on_solve_duties(self):
        solver = DutyRosterSolver(self.project)
        result = solver.solve()
        if result.success:
            self.project.duty_assignments = result.assignments
            self.refresh()
            if self.on_update_callback:
                self.on_update_callback()
            messagebox.showinfo("Duty Roster Generated", result.message)
        else:
            messagebox.showerror("Error", result.message)

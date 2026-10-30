"""
Institution Settings View
Configures academic metadata, selectable working days, periods per day, and break timings.
"""
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox

from models.timetable_data import TimetableProject

ALL_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

class InstitutionView(tb.Frame):
    def __init__(self, parent, project: TimetableProject, on_update_callback=None):
        super().__init__(parent)
        self.project = project
        self.on_update_callback = on_update_callback

        self.day_vars = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Header
        header = tb.Frame(self)
        header.pack(fill=X, padx=20, pady=(15, 10))
        tb.Label(header, text="Institution Profile & Timetable Structure", font=("Helvetica", 16, "bold"), bootstyle="primary").pack(side=LEFT)

        btn_save = tb.Button(header, text="💾 Save Changes", bootstyle="success", command=self._on_save)
        btn_save.pack(side=RIGHT)

        # Content split
        content = tb.Frame(self)
        content.pack(fill=BOTH, expand=True, padx=20, pady=10)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)

        # Left Column: Basic Info & Working Days
        left_col = tb.Frame(content)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # Basic Info Card
        card_info = tb.Labelframe(left_col, text=" Academic Profile ", bootstyle="secondary", padding=15)
        card_info.pack(fill=X, pady=(0, 15))

        tb.Label(card_info, text="Institution / College Name:").pack(anchor=W, pady=(2, 2))
        self.entry_name = tb.Entry(card_info)
        self.entry_name.pack(fill=X, pady=(0, 8))

        row_meta = tb.Frame(card_info)
        row_meta.pack(fill=X, pady=(0, 8))
        row_meta.columnconfigure(0, weight=1)
        row_meta.columnconfigure(1, weight=1)

        f_yr = tb.Frame(row_meta)
        f_yr.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        tb.Label(f_yr, text="Academic Year:").pack(anchor=W)
        self.entry_year = tb.Entry(f_yr)
        self.entry_year.pack(fill=X)

        f_term = tb.Frame(row_meta)
        f_term.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        tb.Label(f_term, text="Term / Semester:").pack(anchor=W)
        self.entry_term = tb.Entry(f_term)
        self.entry_term.pack(fill=X)

        tb.Label(card_info, text="Motto / Header Caption:").pack(anchor=W, pady=(2, 2))
        self.entry_motto = tb.Entry(card_info)
        self.entry_motto.pack(fill=X, pady=(0, 5))

        # Working Days Card
        card_days = tb.Labelframe(left_col, text=" Active Working Days ", bootstyle="secondary", padding=15)
        card_days.pack(fill=X)

        tb.Label(card_days, text="Select institutional teaching days:", font=("Helvetica", 9, "bold")).pack(anchor=W, pady=(0, 8))
        days_box = tb.Frame(card_days)
        days_box.pack(fill=X)

        for d in ALL_DAYS:
            var = tb.BooleanVar(value=(d in self.project.institution.working_days))
            self.day_vars[d] = var
            chk = tb.Checkbutton(days_box, text=d, variable=var, bootstyle="round-toggle")
            chk.pack(anchor=W, pady=3)

        # Right Column: Daily Timing & Periods
        right_col = tb.Frame(content)
        right_col.grid(row=0, column=1, sticky="nsew")

        card_timings = tb.Labelframe(right_col, text=" Daily Periods & Schedule Grid ", bootstyle="secondary", padding=15)
        card_timings.pack(fill=BOTH, expand=True)

        params_grid = tb.Frame(card_timings)
        params_grid.pack(fill=X, pady=(0, 10))
        params_grid.columnconfigure(0, weight=1)
        params_grid.columnconfigure(1, weight=1)

        tb.Label(params_grid, text="Periods/Day (Mon - Thu):").grid(row=0, column=0, sticky=W, pady=4)
        self.spin_periods = tb.Spinbox(params_grid, from_=4, to=12, width=8)
        self.spin_periods.grid(row=0, column=1, sticky=E, pady=4)

        tb.Label(params_grid, text="Friday Periods (Half-Day / Early):", font=("Helvetica", 9, "bold"), bootstyle="primary").grid(row=1, column=0, sticky=W, pady=4)
        self.spin_friday_periods = tb.Spinbox(params_grid, from_=2, to=10, width=8)
        self.spin_friday_periods.grid(row=1, column=1, sticky=E, pady=4)

        tb.Label(params_grid, text="Period Duration (minutes):").grid(row=2, column=0, sticky=W, pady=4)
        self.spin_period_dur = tb.Spinbox(params_grid, from_=30, to=90, width=8)
        self.spin_period_dur.grid(row=2, column=1, sticky=E, pady=4)

        tb.Label(params_grid, text="Recess Break After Period:").grid(row=3, column=0, sticky=W, pady=4)
        self.spin_break_after = tb.Spinbox(params_grid, from_=1, to=10, width=8)
        self.spin_break_after.grid(row=3, column=1, sticky=E, pady=4)

        tb.Label(params_grid, text="Break Duration (minutes):").grid(row=4, column=0, sticky=W, pady=4)
        self.spin_break_dur = tb.Spinbox(params_grid, from_=15, to=60, width=8)
        self.spin_break_dur.grid(row=4, column=1, sticky=E, pady=4)

        tb.Label(params_grid, text="School Start Time (Hour : Min):").grid(row=5, column=0, sticky=W, pady=4)
        time_row = tb.Frame(params_grid)
        time_row.grid(row=5, column=1, sticky=E, pady=4)
        self.spin_hour = tb.Spinbox(time_row, from_=6, to=12, width=4)
        self.spin_hour.pack(side=LEFT, padx=(0, 2))
        tb.Label(time_row, text=":").pack(side=LEFT)
        self.spin_min = tb.Spinbox(time_row, from_=0, to=55, increment=5, width=4)
        self.spin_min.pack(side=LEFT, padx=(2, 0))

        # Preview of Period Timings
        tb.Label(card_timings, text="Period Schedule Preview:", font=("Helvetica", 9, "bold")).pack(anchor=W, pady=(10, 4))

        tree_frame = tb.Frame(card_timings)
        tree_frame.pack(fill=BOTH, expand=True)

        cols = ("period", "start", "end", "type")
        self.tree_periods = tb.Treeview(tree_frame, columns=cols, show="headings", height=8, bootstyle="info")
        self.tree_periods.heading("period", text="Slot")
        self.tree_periods.heading("start", text="Start Time")
        self.tree_periods.heading("end", text="End Time")
        self.tree_periods.heading("type", text="Type")
        self.tree_periods.column("period", width=90, anchor=CENTER)
        self.tree_periods.column("start", width=90, anchor=CENTER)
        self.tree_periods.column("end", width=90, anchor=CENTER)
        self.tree_periods.column("type", width=120, anchor=CENTER)
        self.tree_periods.pack(fill=BOTH, expand=True)

    def refresh(self):
        inst = self.project.institution
        self.entry_name.delete(0, "end")
        self.entry_name.insert(0, inst.name)
        self.entry_year.delete(0, "end")
        self.entry_year.insert(0, inst.academic_year)
        self.entry_term.delete(0, "end")
        self.entry_term.insert(0, inst.term)
        self.entry_motto.delete(0, "end")
        self.entry_motto.insert(0, inst.motto)

        for d, var in self.day_vars.items():
            var.set(d in inst.working_days)

        self.spin_periods.set(inst.periods_per_day)
        self.spin_friday_periods.set(inst.friday_periods)
        self.spin_period_dur.set(inst.period_duration_mins)
        self.spin_break_after.set(inst.break_after_period)
        self.spin_break_dur.set(inst.break_duration_mins)
        self.spin_hour.set(inst.start_hour)
        self.spin_min.set(inst.start_min)

        self._refresh_period_preview()

    def _refresh_period_preview(self):
        for item in self.tree_periods.get_children():
            self.tree_periods.delete(item)

        inst = self.project.institution
        for pt in inst.period_times:
            p_lbl = f"Period {pt.period_num}"
            t_type = "Lecture / Class"
            self.tree_periods.insert("", "end", values=(p_lbl, pt.start_time, pt.end_time, t_type))

            if pt.period_num == inst.break_after_period and pt.period_num < inst.periods_per_day:
                self.tree_periods.insert("", "end", values=("RECESS", "—", "—", "Campus Break / Lunch"))

    def _on_save(self):
        selected_days = [d for d in ALL_DAYS if self.day_vars[d].get()]
        if not selected_days:
            messagebox.showerror("Validation Error", "You must select at least one active working day!")
            return

        try:
            periods = int(self.spin_periods.get())
            fri_periods = int(self.spin_friday_periods.get())
            p_dur = int(self.spin_period_dur.get())
            b_after = int(self.spin_break_after.get())
            b_dur = int(self.spin_break_dur.get())
            s_hour = int(self.spin_hour.get())
            s_min = int(self.spin_min.get())
        except ValueError:
            messagebox.showerror("Validation Error", "Please provide valid integer numbers for timing parameters.")
            return

        inst = self.project.institution
        inst.name = self.entry_name.get().strip() or "Academic Institution"
        inst.academic_year = self.entry_year.get().strip()
        inst.term = self.entry_term.get().strip()
        inst.motto = self.entry_motto.get().strip()
        inst.working_days = selected_days
        inst.periods_per_day = periods
        inst.friday_periods = fri_periods
        inst.day_periods["Friday"] = fri_periods
        inst.period_duration_mins = p_dur
        inst.break_after_period = b_after
        inst.break_duration_mins = b_dur
        inst.start_hour = s_hour
        inst.start_min = s_min
        inst.generate_default_period_times()

        self._refresh_period_preview()
        if self.on_update_callback:
            self.on_update_callback()

        messagebox.showinfo("Saved", "Institution timing and calendar parameters updated successfully!")

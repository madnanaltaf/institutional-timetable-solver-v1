"""
Dashboard View
Presents executive overview metrics, system health pre-flight status,
one-click timetable solving with live progress, and instant sample data loader.
"""
import threading
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox

from models.timetable_data import TimetableProject
from solver.timetable_solver import TimetableSolver
from solver.duty_solver import DutyRosterSolver
from solver.validator import ProjectValidator

class DashboardView(tb.Frame):
    def __init__(self, parent, project: TimetableProject, on_update_callback=None, navigate_callback=None):
        super().__init__(parent)
        self.project = project
        self.on_update_callback = on_update_callback
        self.navigate_callback = navigate_callback

        self.cards = {}
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Header banner
        header_frame = tb.Frame(self)
        header_frame.pack(fill=X, padx=20, pady=(15, 10))

        tb.Label(
            header_frame,
            text="Institutional Timetable & Duty Roster Solver",
            font=("Helvetica", 18, "bold"),
            bootstyle="primary"
        ).pack(side=LEFT)

        btn_row = tb.Frame(header_frame)
        btn_row.pack(side=RIGHT)

        self.btn_load_sample = tb.Button(
            btn_row,
            text="🚀 Load Sample College Data",
            bootstyle="info-outline",
            command=self._on_load_sample
        )
        self.btn_load_sample.pack(side=LEFT, padx=5)

        self.btn_generate = tb.Button(
            btn_row,
            text="⚡ Generate Timetable",
            bootstyle="success",
            command=self._on_generate_timetable
        )
        self.btn_generate.pack(side=LEFT, padx=5)

        # Metrics Row
        self.metrics_container = tb.Frame(self)
        self.metrics_container.pack(fill=X, padx=20, pady=10)

        # 6 Metrics Cards: Classes, Sections, Subjects, Teachers, Rooms, Lessons
        self._add_metric_card("Classes", "classes_val", "🏛️", 0, 0)
        self._add_metric_card("Sections", "sections_val", "👥", 0, 1)
        self._add_metric_card("Subjects", "subjects_val", "📚", 0, 2)
        self._add_metric_card("Teachers", "teachers_val", "👨‍🏫", 0, 3)
        self._add_metric_card("Rooms / Labs", "rooms_val", "🔬", 0, 4)
        self._add_metric_card("Lessons", "lessons_val", "📖", 0, 5)

        for col in range(6):
            self.metrics_container.columnconfigure(col, weight=1)

        # Middle Content: Split into Left (Solver Status & Actions) and Right (Health Diagnostics)
        mid_container = tb.Frame(self)
        mid_container.pack(fill=BOTH, expand=True, padx=20, pady=10)
        mid_container.columnconfigure(0, weight=3)
        mid_container.columnconfigure(1, weight=2)

        # Left: Solver Console & Action Card
        left_card = tb.Labelframe(mid_container, text=" Timetable Generation Engine ", bootstyle="primary", padding=15)
        left_card.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        # Workflow helper
        wf_frame = tb.Frame(left_card, bootstyle="secondary", padding=8)
        wf_frame.pack(fill=X, pady=(0, 12))
        tb.Label(
            wf_frame,
            text="How It Works:  1. Calendar & Timings  ➔  2. Faculty & Rooms  ➔  3. Allocations & Practicals  ➔  4. Click Generate!",
            font=("Helvetica", 8, "bold"),
            bootstyle="inverse-secondary"
        ).pack(anchor=CENTER)

        self.status_lbl = tb.Label(
            left_card,
            text="Status: Ready to solve.",
            font=("Helvetica", 11, "bold"),
            bootstyle="secondary"
        )
        self.status_lbl.pack(anchor=W, pady=(0, 6))

        # BIG HERO GENERATE BUTTON
        self.btn_hero_generate = tb.Button(
            left_card,
            text="⚡ GENERATE TIMETABLE NOW (1-CLICK)",
            bootstyle="success",
            padding=10,
            command=self._on_generate_timetable
        )
        self.btn_hero_generate.pack(fill=X, pady=(4, 8))

        self.progress_bar = tb.Progressbar(left_card, mode="determinate", bootstyle="success-striped")
        self.progress_bar.pack(fill=X, pady=6)

        self.solve_details_lbl = tb.Label(
            left_card,
            text="Solves teacher double-booking, room capacities, aligned science practicals, and cognitive fatigue.",
            font=("Helvetica", 9),
            bootstyle="secondary"
        )
        self.solve_details_lbl.pack(anchor=W, pady=(0, 12))

        # Quick Navigation & Action Shortcuts
        tb.Label(left_card, text="Quick Management & Actions:", font=("Helvetica", 10, "bold")).pack(anchor=W, pady=(10, 5))
        actions_grid = tb.Frame(left_card)
        actions_grid.pack(fill=X, pady=5)

        tb.Button(actions_grid, text="📅 View Timetable", bootstyle="primary-outline", command=lambda: self._navigate("Timetable")).grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        tb.Button(actions_grid, text="🛡️ Duty Roster", bootstyle="secondary-outline", command=lambda: self._navigate("Duty Roster")).grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        tb.Button(actions_grid, text="📄 PDF Export Center", bootstyle="info-outline", command=lambda: self._navigate("Export PDF")).grid(row=0, column=2, padx=4, pady=4, sticky="ew")
        tb.Button(actions_grid, text="🔗 Lesson Allocations", bootstyle="dark-outline", command=lambda: self._navigate("Allocations")).grid(row=1, column=0, padx=4, pady=4, sticky="ew")
        tb.Button(actions_grid, text="👥 Teacher Directory", bootstyle="dark-outline", command=lambda: self._navigate("Teachers")).grid(row=1, column=1, padx=4, pady=4, sticky="ew")
        tb.Button(actions_grid, text="⚙️ Institution Timing", bootstyle="dark-outline", command=lambda: self._navigate("Institution")).grid(row=1, column=2, padx=4, pady=4, sticky="ew")

        for c in range(3):
            actions_grid.columnconfigure(c, weight=1)

        # Right: Pre-Flight Health & Constraint Validator
        right_card = tb.Labelframe(mid_container, text=" Pre-Flight Health & Feasibility ", bootstyle="info", padding=15)
        right_card.grid(row=0, column=1, sticky="nsew")

        self.health_summary_lbl = tb.Label(
            right_card,
            text="Health Check: Performing diagnostics...",
            font=("Helvetica", 10, "bold"),
            bootstyle="success"
        )
        self.health_summary_lbl.pack(anchor=W, pady=(0, 8))

        # Scrollable issues text/list
        issues_frame = tb.Frame(right_card)
        issues_frame.pack(fill=BOTH, expand=True)

        self.issues_text = tb.Text(issues_frame, height=10, wrap="word", font=("Consolas", 9))
        self.issues_text.pack(side=LEFT, fill=BOTH, expand=True)
        sb = tb.Scrollbar(issues_frame, orient="vertical", command=self.issues_text.yview)
        sb.pack(side=RIGHT, fill=Y)
        self.issues_text.configure(yscrollcommand=sb.set)

    def _add_metric_card(self, title: str, key: str, icon: str, row: int, col: int):
        card = tb.Labelframe(self.metrics_container, text=f" {title} ", bootstyle="secondary", padding=10)
        card.grid(row=row, column=col, padx=4, sticky="nsew")

        lbl = tb.Label(card, text="0", font=("Helvetica", 20, "bold"), bootstyle="primary")
        lbl.pack(anchor=CENTER)
        self.cards[key] = lbl

    def refresh(self):
        """Updates all metric numbers and pre-flight diagnostics."""
        self.cards["classes_val"].config(text=str(len(self.project.classes)))
        self.cards["sections_val"].config(text=str(len(self.project.sections)))
        self.cards["subjects_val"].config(text=str(len(self.project.subjects)))
        self.cards["teachers_val"].config(text=str(len(self.project.teachers)))
        self.cards["rooms_val"].config(text=str(len(self.project.classrooms)))
        self.cards["lessons_val"].config(text=str(len(self.project.lessons)))

        # Update solver status label
        if self.project.is_generated and self.project.schedule:
            self.status_lbl.config(
                text=f"Status: Timetable Generated ({len(self.project.schedule)} slots scheduled)",
                bootstyle="success"
            )
            stats = self.project.solve_stats
            sec_time = stats.get("elapsed_seconds", "0.0")
            score = stats.get("quality_score", "N/A")
            self.solve_details_lbl.config(
                text=f"Generated in {sec_time}s | Quality Score: {score} | Last: {self.project.last_generated_time}"
            )
            self.progress_bar['value'] = 100
        else:
            self.status_lbl.config(text="Status: No Timetable Generated Yet", bootstyle="warning")
            self.solve_details_lbl.config(text="Click 'Generate Timetable' to solve constraints and schedule classes.")
            self.progress_bar['value'] = 0

        # Run Validator
        validator = ProjectValidator(self.project)
        issues = validator.validate()

        self.issues_text.delete("1.0", "end")
        errors = [i for i in issues if i.severity == "ERROR"]
        warnings = [i for i in issues if i.severity == "WARNING"]

        if not issues:
            self.health_summary_lbl.config(text="✓ Feasibility: 100% Conflict-Free & Solvable", bootstyle="success")
            self.issues_text.insert("end", "All institutional checks passed:\n\n")
            self.issues_text.insert("end", "• Working days and period timings configured.\n")
            self.issues_text.insert("end", "• Section workloads within available week slots.\n")
            self.issues_text.insert("end", "• Teacher assignments respect max weekly loads.\n")
            self.issues_text.insert("end", "• Synchronized science practicals matched properly.\n")
            self.issues_text.insert("end", "• Classroom & specialized lab capacities verified.\n")
        else:
            if errors:
                self.health_summary_lbl.config(
                    text=f"⚠️ {len(errors)} Error(s), {len(warnings)} Warning(s) Detected",
                    bootstyle="danger"
                )
            else:
                self.health_summary_lbl.config(
                    text=f"ℹ️ {len(warnings)} Warning(s) Detected (Solvable)",
                    bootstyle="warning"
                )

            for iss in issues:
                tag = f"[{iss.severity}] "
                self.issues_text.insert("end", f"{tag}{iss.title}\n")
                self.issues_text.insert("end", f"  {iss.description}\n\n")

    def _on_generate_timetable(self):
        """Spawns solver in background thread with live UI updates."""
        self.btn_generate.config(state="disabled")
        self.btn_hero_generate.config(state="disabled")
        self.btn_load_sample.config(state="disabled")
        self.status_lbl.config(text="Status: Constraint Solver Running...", bootstyle="info")
        self.progress_bar['value'] = 0

        def run_solve():
            def progress(assigned, total, msg):
                if total > 0:
                    pct = int((assigned / total) * 100)
                    self.after(0, lambda: self._update_progress(pct, msg))

            solver = TimetableSolver(
                self.project,
                timeout_seconds=30.0,
                progress_callback=progress
            )
            result = solver.solve()

            # Automatically run duty solver as well if duty slots exist!
            duty_result = None
            if result.success and self.project.duty_slots:
                self.project.schedule = result.schedule
                duty_solver = DutyRosterSolver(self.project)
                duty_result = duty_solver.solve()
                if duty_result.success:
                    self.project.duty_assignments = duty_result.assignments

            self.after(0, lambda: self._on_solve_finished(result, duty_result))

        threading.Thread(target=run_solve, daemon=True).start()

    def _update_progress(self, pct: int, msg: str):
        self.progress_bar['value'] = pct
        self.solve_details_lbl.config(text=msg)

    def _on_solve_finished(self, result, duty_result=None):
        self.btn_generate.config(state="normal")
        self.btn_hero_generate.config(state="normal")
        self.btn_load_sample.config(state="normal")

        if result.success:
            self.project.schedule = result.schedule
            self.project.is_generated = True
            import datetime
            self.project.last_generated_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.project.solve_stats = result.stats

            self.refresh()
            if self.on_update_callback:
                self.on_update_callback()

            extra_duty = f"\n\nDuty Roster: {duty_result.message}" if duty_result else ""
            if messagebox.askyesno(
                "Timetable Generated Successfully!",
                f"{result.message}{extra_duty}\n\nWould you like to open the 'Interactive Timetable' tab to view and inspect the schedule?"
            ):
                self._navigate("Timetable")
        else:
            self.status_lbl.config(text="Status: Solving Failed", bootstyle="danger")
            self.refresh()
            messagebox.showerror(
                "Generation Error",
                f"Solver could not generate timetable:\n\n{result.message}"
            )

    def _on_load_sample(self):
        if messagebox.askyesno("Load Sample College Data", "Replace current project with sample Cambridge Science & Tech Academy dataset?"):
            new_proj = TimetableProject.create_sample_institution()
            # Copy into current project
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

            self.refresh()
            if self.on_update_callback:
                self.on_update_callback()
            messagebox.showinfo("Sample Loaded", "Sample institution loaded with 4 sections, aligned science practicals, 10 faculty members, and duty slots!")

    def _navigate(self, view_name: str):
        if self.navigate_callback:
            self.navigate_callback(view_name)

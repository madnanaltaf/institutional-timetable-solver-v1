"""
Main Application Window
Provides modern navigation sidebar, unified top action ribbon, dynamic view routing,
and project lifecycle management.
"""
import os
import sys
import threading
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox

from models.timetable_data import TimetableProject
from solver.timetable_solver import TimetableSolver
from solver.duty_solver import DutyRosterSolver
from ui.theme import APP_THEME
from ui.views.dashboard_view import DashboardView
from ui.views.institution_view import InstitutionView
from ui.views.teachers_view import TeachersView
from ui.views.classes_view import ClassesView
from ui.views.rooms_view import RoomsView
from ui.views.subjects_view import SubjectsView
from ui.views.lessons_view import LessonsView
from ui.views.timetable_view import TimetableView
from ui.views.duty_roster_view import DutyRosterView
from ui.views.export_view import ExportView

NAV_ITEMS = [
    ("Dashboard", "📊  Dashboard"),
    ("Timetable", "📅  Interactive Timetable"),
    ("Allocations", "📖  Class Period Allotment"),
    ("Teachers", "👥  Faculty & Teachers"),
    ("Classes", "🏛️  Classes & Sections"),
    ("Subjects", "📚  Subjects & Curriculum"),
    ("Rooms", "🔬  Rooms & Laboratories"),
    ("Institution", "⚙️  Institution & Calendar"),
    ("Duty Roster", "🛡️  Duty & Invigilation"),
    ("Export PDF", "📄  Export Center (PDF)")
]

class TimetableApplication(tb.Window):
    def __init__(self, initial_project_file: str = None):
        super().__init__(
            title="Institutional Timetable & Duty Roster Constraint Solver",
            themename=APP_THEME,
            size=(1320, 840),
            minsize=(1100, 700)
        )

        self.current_project_file = initial_project_file
        if initial_project_file and os.path.exists(initial_project_file):
            self.project = TimetableProject.load_from_file(initial_project_file)
        else:
            sample_path = os.path.join("sample_data", "college_sample.json")
            if os.path.exists(sample_path):
                self.project = TimetableProject.load_from_file(sample_path)
            else:
                self.project = TimetableProject.create_sample_institution()

        self.views = {}
        self.nav_buttons = {}
        self.current_view_name = "Dashboard"

        self._build_menu()
        self._build_layout()
        self._switch_view("Dashboard")

    def _build_menu(self):
        menubar = tb.Menu(self)

        # File Menu
        file_menu = tb.Menu(menubar, tearoff=0)
        file_menu.add_command(label="➕ New Project", command=self._on_new_project)
        file_menu.add_command(label="📂 Open Project...", command=self._on_open_project)
        file_menu.add_command(label="💾 Save Project", command=self._on_save_project)
        file_menu.add_command(label="💾 Save Project As...", command=self._on_save_as_project)
        file_menu.add_separator()
        file_menu.add_command(label="🚀 Load Sample College Data", command=self._on_load_sample)
        file_menu.add_separator()
        file_menu.add_command(label="❌ Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Solve Menu
        solve_menu = tb.Menu(menubar, tearoff=0)
        solve_menu.add_command(label="⚡ Generate Full Timetable", command=self._on_global_generate)
        solve_menu.add_command(label="🛡️ Generate Fair Duty Roster", command=lambda: self._switch_view("Duty Roster"))
        menubar.add_cascade(label="Solve", menu=solve_menu)

        # Export Menu
        export_menu = tb.Menu(menubar, tearoff=0)
        export_menu.add_command(label="📄 PDF Export Center...", command=lambda: self._switch_view("Export PDF"))
        menubar.add_cascade(label="Export", menu=export_menu)

        # Help Menu
        help_menu = tb.Menu(menubar, tearoff=0)
        help_menu.add_command(label="ℹ️ About Constraint Solver", command=self._on_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.config(menu=menubar)

    def _build_layout(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ------------------ Left Sidebar ------------------ #
        sidebar = tb.Frame(self, bootstyle="dark", width=240, padding=10)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.pack_propagate(False)

        # Brand Logo / Title
        brand_frame = tb.Frame(sidebar, bootstyle="dark")
        brand_frame.pack(fill=X, pady=(5, 10))

        tb.Label(
            brand_frame,
            text="TIMETABLE",
            font=("Helvetica", 14, "bold"),
            bootstyle="inverse-dark"
        ).pack(anchor=W)

        tb.Label(
            brand_frame,
            text="Constraint Solver 2.0",
            font=("Helvetica", 8, "italic"),
            bootstyle="inverse-dark"
        ).pack(anchor=W)

        # Prominent Persistent Generate Button on Sidebar
        self.btn_sidebar_gen = tb.Button(
            sidebar,
            text="⚡ GENERATE TIMETABLE",
            bootstyle="success",
            cursor="hand2",
            padding=8,
            command=self._on_global_generate
        )
        self.btn_sidebar_gen.pack(fill=X, pady=(6, 12))

        tb.Separator(sidebar, bootstyle="secondary").pack(fill=X, pady=(0, 8))

        # Navigation Buttons
        for key, label in NAV_ITEMS:
            btn = tb.Button(
                sidebar,
                text=label,
                bootstyle="secondary-outline",
                cursor="hand2",
                command=lambda k=key: self._switch_view(k)
            )
            btn.pack(fill=X, pady=2)
            self.nav_buttons[key] = btn

        # Bottom Sidebar Quick Info
        tb.Separator(sidebar, bootstyle="secondary").pack(fill=X, pady=(15, 10), side=BOTTOM)
        self.lbl_sidebar_info = tb.Label(
            sidebar,
            text="Cambridge Science Academy\nFall Semester 2026-2027",
            font=("Helvetica", 8),
            bootstyle="inverse-dark"
        )
        self.lbl_sidebar_info.pack(anchor=W, side=BOTTOM, fill=X)

        # ------------------ Right Main Area (Top Ribbon + View) ------------------ #
        right_main = tb.Frame(self)
        right_main.grid(row=0, column=1, sticky="nsew")
        right_main.columnconfigure(0, weight=1)
        right_main.rowconfigure(1, weight=1)

        # 1. Global Persistent Top Action Ribbon
        top_ribbon = tb.Frame(right_main, bootstyle="light", padding=(15, 8))
        top_ribbon.grid(row=0, column=0, sticky="ew")

        # Ribbon Left: Title & Live Status Badge
        ribbon_left = tb.Frame(top_ribbon, bootstyle="light")
        ribbon_left.pack(side=LEFT)

        self.lbl_ribbon_inst = tb.Label(
            ribbon_left,
            text=self.project.institution.name,
            font=("Helvetica", 11, "bold"),
            bootstyle="primary"
        )
        self.lbl_ribbon_inst.pack(anchor=W)

        self.lbl_ribbon_status = tb.Label(
            ribbon_left,
            text="Status: Ready to solve",
            font=("Helvetica", 8, "bold"),
            bootstyle="secondary"
        )
        self.lbl_ribbon_status.pack(anchor=W)

        # Ribbon Right: Global Instant Action Buttons
        ribbon_right = tb.Frame(top_ribbon, bootstyle="light")
        ribbon_right.pack(side=RIGHT)

        # BIG PROMINENT GENERATE BUTTON
        self.btn_ribbon_gen = tb.Button(
            ribbon_right,
            text="⚡ GENERATE TIMETABLE",
            bootstyle="success",
            cursor="hand2",
            padding=(14, 6),
            command=self._on_global_generate
        )
        self.btn_ribbon_gen.pack(side=LEFT, padx=(0, 6))

        tb.Button(
            ribbon_right,
            text="🛡️ Duty Roster",
            bootstyle="secondary-outline",
            command=lambda: self._switch_view("Duty Roster")
        ).pack(side=LEFT, padx=(0, 4))

        tb.Button(
            ribbon_right,
            text="📄 Export PDFs",
            bootstyle="info-outline",
            command=lambda: self._switch_view("Export PDF")
        ).pack(side=LEFT, padx=(0, 4))

        tb.Button(
            ribbon_right,
            text="🚀 Load Sample",
            bootstyle="primary-outline",
            command=self._on_load_sample
        ).pack(side=LEFT, padx=(0, 4))

        tb.Button(
            ribbon_right,
            text="💾 Save",
            bootstyle="dark-outline",
            command=self._on_save_project
        ).pack(side=LEFT)

        # 2. Content Container (Views)
        self.content_container = tb.Frame(right_main)
        self.content_container.grid(row=1, column=0, sticky="nsew")
        self.content_container.columnconfigure(0, weight=1)
        self.content_container.rowconfigure(0, weight=1)

        # Instantiate all Views
        self.views["Dashboard"] = DashboardView(self.content_container, self.project, on_update_callback=self._on_project_modified, navigate_callback=self._switch_view)
        self.views["Timetable"] = TimetableView(self.content_container, self.project, on_update_callback=self._on_project_modified)
        self.views["Institution"] = InstitutionView(self.content_container, self.project, on_update_callback=self._on_project_modified)
        self.views["Teachers"] = TeachersView(self.content_container, self.project, on_update_callback=self._on_project_modified)
        self.views["Classes"] = ClassesView(self.content_container, self.project, on_update_callback=self._on_project_modified)
        self.views["Rooms"] = RoomsView(self.content_container, self.project, on_update_callback=self._on_project_modified)
        self.views["Subjects"] = SubjectsView(self.content_container, self.project, on_update_callback=self._on_project_modified)
        self.views["Allocations"] = LessonsView(self.content_container, self.project, on_update_callback=self._on_project_modified)
        self.views["Duty Roster"] = DutyRosterView(self.content_container, self.project, on_update_callback=self._on_project_modified)
        self.views["Export PDF"] = ExportView(self.content_container, self.project)

        # ------------------ Bottom Status Bar ------------------ #
        status_bar = tb.Frame(self, bootstyle="secondary", padding=4)
        status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")

        self.lbl_status_file = tb.Label(
            status_bar,
            text=f"Project: {os.path.basename(self.current_project_file) if self.current_project_file else 'Untitled Project'}",
            font=("Helvetica", 8),
            bootstyle="inverse-secondary"
        )
        self.lbl_status_file.pack(side=LEFT, padx=10)

        self.lbl_status_info = tb.Label(
            status_bar,
            text="Ready  |  Constraint Solver: Operational",
            font=("Helvetica", 8),
            bootstyle="inverse-secondary"
        )
        self.lbl_status_info.pack(side=RIGHT, padx=10)

    def _switch_view(self, view_name: str):
        if view_name not in self.views:
            return

        self.current_view_name = view_name

        # Update button styles
        for k, btn in self.nav_buttons.items():
            if k == view_name:
                btn.configure(bootstyle="primary")
            else:
                btn.configure(bootstyle="secondary-outline")

        # Hide all views and show target
        for v in self.views.values():
            v.grid_forget()

        target = self.views[view_name]
        target.grid(row=0, column=0, sticky="nsew")
        if hasattr(target, "refresh"):
            target.refresh()

    def _on_global_generate(self):
        """Global 1-click generation from top ribbon or sidebar."""
        self.btn_ribbon_gen.config(state="disabled", text="⏳ Solving...")
        self.btn_sidebar_gen.config(state="disabled", text="⏳ Solving...")
        self.lbl_status_info.config(text="Running multi-objective constraint solver...")

        def solve_thread():
            solver = TimetableSolver(self.project, timeout_seconds=30.0)
            res = solver.solve()

            duty_res = None
            if res.success and self.project.duty_slots:
                self.project.schedule = res.schedule
                duty_solver = DutyRosterSolver(self.project)
                duty_res = duty_solver.solve()
                if duty_res.success:
                    self.project.duty_assignments = duty_res.assignments

            self.after(0, lambda: self._on_global_solve_complete(res, duty_res))

        threading.Thread(target=solve_thread, daemon=True).start()

    def _on_global_solve_complete(self, res, duty_res=None):
        self.btn_ribbon_gen.config(state="normal", text="⚡ GENERATE TIMETABLE")
        self.btn_sidebar_gen.config(state="normal", text="⚡ GENERATE TIMETABLE")

        if res.success:
            self.project.schedule = res.schedule
            self.project.is_generated = True
            import datetime
            self.project.last_generated_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.project.solve_stats = res.stats

            self._on_project_modified()
            self.lbl_status_info.config(text=f"✓ Timetable Solved ({len(res.schedule)} slots scheduled in {res.stats.get('elapsed_seconds', '0.0')}s)")
            self.lbl_ribbon_status.config(
                text=f"✓ Solved ({len(res.schedule)} slots scheduled)",
                bootstyle="success"
            )

            # Automatically navigate to Interactive Timetable view so the user immediately sees it!
            self._switch_view("Timetable")

            extra = f"\n\nDuty Roster: {duty_res.message}" if duty_res else ""
            messagebox.showinfo(
                "Timetable Generated Successfully!",
                f"{res.message}{extra}\n\n"
                "You are now on the 'Interactive Timetable' tab!\n"
                "• Toggle between Class, Teacher, Room, and Master Matrix views.\n"
                "• Click any cell to inspect or manually edit/move slots.\n"
                "• Click 'Export to PDF' to generate publication-ready schedules!"
            )
        else:
            self.lbl_status_info.config(text="Solving failed. Check constraints.")
            self.lbl_ribbon_status.config(text="⚠️ Solving failed", bootstyle="danger")
            messagebox.showerror("Constraint Solver Error", f"Could not solve timetable:\n\n{res.message}")

    def _on_project_modified(self):
        """Called when data is changed in any view to update other views."""
        self.lbl_ribbon_inst.config(text=self.project.institution.name)
        self.lbl_sidebar_info.config(
            text=f"{self.project.institution.name}\n{self.project.institution.academic_year}"
        )
        if self.project.is_generated and self.project.schedule:
            self.lbl_ribbon_status.config(
                text=f"✓ Solved ({len(self.project.schedule)} slots scheduled)",
                bootstyle="success"
            )
        else:
            self.lbl_ribbon_status.config(text="Status: Ready to solve", bootstyle="secondary")

        # Notify other views if they need refresh
        for name, v in self.views.items():
            if name != self.current_view_name and hasattr(v, "refresh"):
                v.refresh()

    def _on_new_project(self):
        if messagebox.askyesno("New Project", "Start a new blank institutional project?"):
            self.project = TimetableProject()
            self.current_project_file = None
            self._reload_all_views()

    def _on_open_project(self):
        filepath = filedialog.askopenfilename(
            title="Open Timetable Project",
            filetypes=[("Timetable Project JSON", "*.json"), ("All Files", "*.*")]
        )
        if filepath:
            try:
                self.project = TimetableProject.load_from_file(filepath)
                self.current_project_file = filepath
                self.lbl_status_file.config(text=f"Project: {os.path.basename(filepath)}")
                self._reload_all_views()
                messagebox.showinfo("Project Loaded", f"Loaded project successfully from:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load project:\n{e}")

    def _on_save_project(self):
        if self.current_project_file:
            self.project.save_to_file(self.current_project_file)
            messagebox.showinfo("Saved", "Project saved successfully!")
        else:
            self._on_save_as_project()

    def _on_save_as_project(self):
        dest = filedialog.asksaveasfilename(
            title="Save Timetable Project As",
            defaultextension=".json",
            filetypes=[("Timetable Project JSON", "*.json")]
        )
        if dest:
            self.project.save_to_file(dest)
            self.current_project_file = dest
            self.lbl_status_file.config(text=f"Project: {os.path.basename(dest)}")
            messagebox.showinfo("Saved", f"Project saved to:\n{dest}")

    def _on_load_sample(self):
        if messagebox.askyesno("Load Sample Data", "Load the pre-configured Cambridge Science & Tech Academy dataset?"):
            self.project = TimetableProject.create_sample_institution()
            self.current_project_file = "sample_data/college_sample.json"
            self.lbl_status_file.config(text="Project: Cambridge Science Academy (Sample)")
            self._reload_all_views()
            messagebox.showinfo("Sample Loaded", "Sample institution loaded with 4 sections, aligned science practicals, 10 faculty members, and duty slots!")

    def _reload_all_views(self):
        for v in self.views.values():
            v.project = self.project
            if hasattr(v, "refresh"):
                v.refresh()
        self._on_project_modified()

    def _on_about(self):
        messagebox.showinfo(
            "About Timetable Constraint Solver",
            "Institutional Timetable & Duty Roster Constraint Solver 2.0\n\n"
            "Key Features:\n"
            "• Hard Constraint Engine (No teacher double-booking, room capacity, multi-period continuity)\n"
            "• Aligned Science & Computer Practicals (Parallel sections synchronized swap)\n"
            "• Cognitive Fatigue Avoidance & Subject Dispersion\n"
            "• Fair-Share Invigilation & Campus Duty Roster balancing\n"
            "• Publication-Ready PDF export (Teacher, Class, Section, Subject, Master & Duty)"
        )

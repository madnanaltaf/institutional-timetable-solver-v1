"""
Institutional Timetable & Duty Roster Constraint Solver
Entry Point for Desktop GUI and Headless Batch Execution.

Usage:
    python main.py                 # Launches the modern desktop UI
    python main.py --cli --solve   # Headless solve and PDF generation
"""
import sys
import os
import argparse

# Ensure current working directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.timetable_data import TimetableProject
from solver.timetable_solver import TimetableSolver
from solver.duty_solver import DutyRosterSolver
from solver.validator import ProjectValidator
from exports.pdf_generator import TimetablePDFGenerator
from exports.excel_exporter import TimetableSpreadsheetExporter

def run_cli(args):
    print("=" * 70)
    print("Institutional Timetable & Duty Roster Constraint Solver (CLI Mode)")
    print("=" * 70)

    # 1. Load project
    project_file = args.project
    if project_file and os.path.exists(project_file):
        print(f"Loading project from: {project_file}")
        project = TimetableProject.load_from_file(project_file)
    else:
        sample_path = os.path.join("sample_data", "college_sample.json")
        if os.path.exists(sample_path):
            print(f"Loading default sample: {sample_path}")
            project = TimetableProject.load_from_file(sample_path)
        else:
            print("Generating built-in sample college dataset...")
            project = TimetableProject.create_sample_institution()

    print(f"Institution: {project.institution.name}")
    print(f"Working Days: {', '.join(project.institution.working_days)} ({project.institution.periods_per_day} periods/day)")
    print(f"Classes/Sections: {len(project.sections)} | Teachers: {len(project.teachers)} | Lessons: {len(project.lessons)}")

    # 2. Pre-flight validation
    print("\nRunning pre-flight feasibility diagnostics...")
    validator = ProjectValidator(project)
    issues = validator.validate()
    errors = [i for i in issues if i.severity == "ERROR"]
    warnings = [i for i in issues if i.severity == "WARNING"]

    print(f"Diagnostics: {len(errors)} error(s), {len(warnings)} warning(s)")
    for w in warnings:
        print(f"  [WARNING] {w.title}: {w.description}")
    for e in errors:
        print(f"  [ERROR] {e.title}: {e.description}")

    if errors:
        print("\nPre-flight checks failed. Please resolve errors before solving.")
        sys.exit(1)

    # 3. Solve Timetable
    print("\nLaunching constraint satisfaction solver...")
    solver = TimetableSolver(project, timeout_seconds=args.timeout)
    res = solver.solve()

    if not res.success:
        print(f"Solving Failed: {res.message}")
        sys.exit(1)

    project.schedule = res.schedule
    project.is_generated = True
    print(f"Success! {res.message}")
    print(f"Quality Score: {res.stats.get('quality_score')} (Lower = Better)")

    # 4. Solve Duty Roster
    if project.duty_slots:
        print("\nSolving Fair-Share Duty Roster & Invigilation...")
        duty_solver = DutyRosterSolver(project)
        d_res = duty_solver.solve()
        if d_res.success:
            project.duty_assignments = d_res.assignments
            print(f"Duty Roster: {d_res.message}")

    # 5. Export Schedules
    export_dir = args.export_dir or "exports_out"
    os.makedirs(export_dir, exist_ok=True)
    print(f"\nGenerating publication-ready PDF and CSV documents into: {export_dir}")

    pdf_gen = TimetablePDFGenerator(project)

    p_sec = os.path.join(export_dir, "Class_Sections_Timetable_Booklet.pdf")
    pdf_gen.export_section_timetables_pdf(p_sec)
    print(f"  ✓ {p_sec}")

    p_teach = os.path.join(export_dir, "Faculty_Teachers_Timetable_Booklet.pdf")
    pdf_gen.export_teacher_timetables_pdf(p_teach)
    print(f"  ✓ {p_teach}")

    p_master = os.path.join(export_dir, "Master_Institutional_Matrix.pdf")
    pdf_gen.export_master_timetable_pdf(p_master)
    print(f"  ✓ {p_master}")

    p_sub = os.path.join(export_dir, "Subject_Schedules_Report.pdf")
    pdf_gen.export_subject_schedules_pdf(p_sub)
    print(f"  ✓ {p_sub}")

    if project.duty_assignments:
        p_duty = os.path.join(export_dir, "Staff_Duty_Roster.pdf")
        pdf_gen.export_duty_roster_pdf(p_duty)
        print(f"  ✓ {p_duty}")

    csv_gen = TimetableSpreadsheetExporter(project)
    csv_master = os.path.join(export_dir, "Master_Timetable.csv")
    csv_gen.export_master_csv(csv_master)
    print(f"  ✓ {csv_master}")

    if project.duty_assignments:
        csv_duty = os.path.join(export_dir, "Staff_Duty_Roster.csv")
        csv_gen.export_duty_roster_csv(csv_duty)
        print(f"  ✓ {csv_duty}")

    # Save solved project JSON
    out_proj = os.path.join(export_dir, "solved_timetable_project.json")
    project.save_to_file(out_proj)
    print(f"  ✓ {out_proj}")

    print("\n" + "=" * 70)
    print("All schedules generated successfully!")
    print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="Institutional Timetable & Duty Roster Constraint Solver")
    parser.add_argument("--cli", action="store_true", help="Run in headless CLI mode instead of GUI")
    parser.add_argument("--project", type=str, help="Path to project JSON file")
    parser.add_argument("--export-dir", type=str, default="exports_out", help="Directory to save generated PDFs")
    parser.add_argument("--timeout", type=float, default=25.0, help="Solver timeout in seconds")

    args = parser.parse_args()

    if args.cli:
        run_cli(args)
    else:
        # Launch modern GUI
        from ui.app_window import TimetableApplication
        app = TimetableApplication(initial_project_file=args.project)
        app.mainloop()

if __name__ == "__main__":
    main()

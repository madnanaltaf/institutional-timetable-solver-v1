"""
PDF & Spreadsheet Export Control Center
Generates high-resolution publication-ready PDF documents:
- Teacher-wise timetables (individual or compilation booklet)
- Class & Section-wise timetables
- Subject-wise schedules
- Master institutional matrix
- Duty roster and invigilation schedules
- CSV/Excel formats
"""
import os
import subprocess
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import filedialog, messagebox

from models.timetable_data import TimetableProject
from exports.pdf_generator import TimetablePDFGenerator
from exports.excel_exporter import TimetableSpreadsheetExporter

class ExportView(tb.Frame):
    def __init__(self, parent, project: TimetableProject):
        super().__init__(parent)
        self.project = project
        self.last_exported_file = None

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Header
        header = tb.Frame(self)
        header.pack(fill=X, padx=20, pady=(15, 10))

        tb.Label(header, text="Publication & Export Control Center", font=("Helvetica", 16, "bold"), bootstyle="primary").pack(side=LEFT)

        btn_box = tb.Frame(header)
        btn_box.pack(side=RIGHT)

        self.btn_open_folder = tb.Button(
            btn_box,
            text="📂 Open Export Folder",
            bootstyle="secondary-outline",
            command=self._open_export_dir
        )
        self.btn_open_folder.pack(side=LEFT, padx=5)

        self.btn_open_file = tb.Button(
            btn_box,
            text="🚀 View Last Exported PDF",
            bootstyle="info-outline",
            state="disabled",
            command=self._open_last_file
        )
        self.btn_open_file.pack(side=LEFT)

        # 2-Column Grid of Export Options
        content = tb.Frame(self)
        content.pack(fill=BOTH, expand=True, padx=20, pady=10)
        content.columnconfigure(0, weight=1)
        content.columnconfigure(1, weight=1)

        # Card 1: Section-Wise Timetable PDF
        c1 = tb.Labelframe(content, text=" 🏫 Class & Section Timetables PDF ", bootstyle="primary", padding=15)
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 10), pady=(0, 15))

        tb.Label(c1, text="Generates elegant timetables for students with subject legend, teacher names, and room numbers.").pack(anchor=W, pady=(0, 8))

        row_s = tb.Frame(c1)
        row_s.pack(fill=X, pady=(0, 10))
        tb.Label(row_s, text="Scope:").pack(side=LEFT, padx=(0, 5))
        self.combo_sec_scope = tb.Combobox(row_s, state="readonly", width=32)
        self.combo_sec_scope.pack(side=LEFT, fill=X, expand=True)

        tb.Button(c1, text="📄 Export Class Timetable PDF", bootstyle="primary", command=self._export_section_pdf).pack(anchor=E)

        # Card 2: Teacher-Wise Timetable PDF
        c2 = tb.Labelframe(content, text=" 👤 Faculty & Teacher Timetables PDF ", bootstyle="success", padding=15)
        c2.grid(row=0, column=1, sticky="nsew", pady=(0, 15))

        tb.Label(c2, text="Individual schedules for faculty members with weekly teaching load and assigned campus duties.").pack(anchor=W, pady=(0, 8))

        row_t = tb.Frame(c2)
        row_t.pack(fill=X, pady=(0, 10))
        tb.Label(row_t, text="Scope:").pack(side=LEFT, padx=(0, 5))
        self.combo_teach_scope = tb.Combobox(row_t, state="readonly", width=32)
        self.combo_teach_scope.pack(side=LEFT, fill=X, expand=True)

        tb.Button(c2, text="📄 Export Teacher Timetable PDF", bootstyle="success", command=self._export_teacher_pdf).pack(anchor=E)

        # Card 3: Master Institutional Panoramic Matrix PDF (By Day)
        c3 = tb.Labelframe(content, text=" 🌐 Master Institutional Matrices (By Day) ", bootstyle="info", padding=15)
        c3.grid(row=1, column=0, sticky="nsew", padx=(0, 10), pady=(0, 15))

        tb.Label(c3, text="Master schedules by day (Monday to Friday/Saturday). Each day on its own dedicated A4 page with guaranteed margins.").pack(anchor=W, pady=(0, 8))

        btn_matrix_box = tb.Frame(c3)
        btn_matrix_box.pack(anchor=E)
        tb.Button(btn_matrix_box, text="📄 Class Matrix (By Day)", bootstyle="info", command=self._export_master_pdf).pack(side=LEFT, padx=(0, 6))
        tb.Button(btn_matrix_box, text="📄 Faculty Matrix (By Day)", bootstyle="primary-outline", command=self._export_faculty_matrix_pdf).pack(side=LEFT)

        # Card 4: Duty Roster & Invigilation PDF
        c4 = tb.Labelframe(content, text=" 🛡️ Staff Duty Roster & Invigilation PDF ", bootstyle="warning", padding=15)
        c4.grid(row=1, column=1, sticky="nsew", pady=(0, 15))

        tb.Label(c4, text="Weekly staff duty allocations, exam invigilation lists, and faculty fairness balance audit.").pack(anchor=W, pady=(0, 12))
        tb.Button(c4, text="📄 Export Duty Roster PDF", bootstyle="warning", command=self._export_duty_pdf).pack(anchor=E)

        # Card 5: Subject-Wise Schedule PDF
        c5 = tb.Labelframe(content, text=" 📖 Subject-Wise Curriculum Schedule PDF ", bootstyle="secondary", padding=15)
        c5.grid(row=2, column=0, sticky="nsew", padx=(0, 10))

        tb.Label(c5, text="Master schedule sorted by subject, detailing when science practicals, electives, and lectures take place.").pack(anchor=W, pady=(0, 12))
        tb.Button(c5, text="📄 Export Subject Schedules PDF", bootstyle="secondary", command=self._export_subjects_pdf).pack(anchor=E)

        # Card 6: CSV & Spreadsheet Backups
        c6 = tb.Labelframe(content, text=" 📊 Spreadsheet & Data Export (CSV) ", bootstyle="dark", padding=15)
        c6.grid(row=2, column=1, sticky="nsew")

        tb.Label(c6, text="Raw structured spreadsheets for external database import, Microsoft Excel, or Google Sheets.").pack(anchor=W, pady=(0, 12))
        tb.Button(c6, text="📊 Export CSV Spreadsheets", bootstyle="dark", command=self._export_csv).pack(anchor=E)

    def refresh(self):
        # Populate section scope
        sec_items = ["All Sections (Complete Booklet)"] + [f"{s.display_name} [{s.id}]" for s in self.project.sections.values()]
        self.combo_sec_scope['values'] = sec_items
        self.combo_sec_scope.set(sec_items[0])

        # Populate teacher scope
        t_items = ["All Faculty Members (Full Booklet)"] + [f"{t.name} ({t.code}) [{t.id}]" for t in self.project.teachers.values()]
        self.combo_teach_scope['values'] = t_items
        self.combo_teach_scope.set(t_items[0])

    def _get_export_dir(self) -> str:
        out_dir = os.path.abspath("exports_out")
        os.makedirs(out_dir, exist_ok=True)
        return out_dir

    def _parse_id(self, text: str) -> str:
        if "[" in text and text.endswith("]"):
            return text.split("[")[-1].rstrip("]")
        return ""

    def _export_section_pdf(self):
        if not self._check_schedule():
            return
        scope_str = self.combo_sec_scope.get()
        target_id = self._parse_id(scope_str) if "All" not in scope_str else None

        default_name = f"Class_Timetable_{target_id}.pdf" if target_id else "All_Class_Timetables_Booklet.pdf"
        dest = filedialog.asksaveasfilename(
            initialdir=self._get_export_dir(),
            initialfile=default_name,
            defaultextension=".pdf",
            filetypes=[("PDF Documents", "*.pdf")]
        )
        if not dest:
            return

        gen = TimetablePDFGenerator(self.project)
        gen.export_section_timetables_pdf(dest, target_id)
        self._notify_export_success(dest)

    def _export_teacher_pdf(self):
        if not self._check_schedule():
            return
        scope_str = self.combo_teach_scope.get()
        target_id = self._parse_id(scope_str) if "All" not in scope_str else None

        default_name = f"Teacher_Timetable_{target_id}.pdf" if target_id else "Faculty_Timetables_Booklet.pdf"
        dest = filedialog.asksaveasfilename(
            initialdir=self._get_export_dir(),
            initialfile=default_name,
            defaultextension=".pdf",
            filetypes=[("PDF Documents", "*.pdf")]
        )
        if not dest:
            return

        gen = TimetablePDFGenerator(self.project)
        gen.export_teacher_timetables_pdf(dest, target_id)
        self._notify_export_success(dest)

    def _export_master_pdf(self):
        if not self._check_schedule():
            return
        dest = filedialog.asksaveasfilename(
            initialdir=self._get_export_dir(),
            initialfile="Master_Institutional_Matrix.pdf",
            defaultextension=".pdf",
            filetypes=[("PDF Documents", "*.pdf")]
        )
        if not dest:
            return

        gen = TimetablePDFGenerator(self.project)
        gen.export_master_timetable_pdf(dest)
        self._notify_export_success(dest)

    def _export_faculty_matrix_pdf(self):
        if not self._check_schedule():
            return
        dest = filedialog.asksaveasfilename(
            initialdir=self._get_export_dir(),
            initialfile="Master_Faculty_Matrix_By_Day.pdf",
            defaultextension=".pdf",
            filetypes=[("PDF Documents", "*.pdf")]
        )
        if not dest:
            return

        gen = TimetablePDFGenerator(self.project)
        gen.export_master_faculty_matrix_by_day_pdf(dest)
        self._notify_export_success(dest)

    def _export_duty_pdf(self):
        if not self.project.duty_assignments:
            messagebox.showwarning("Warning", "No duty assignments to export. Generate duty roster first.")
            return
        dest = filedialog.asksaveasfilename(
            initialdir=self._get_export_dir(),
            initialfile="Staff_Duty_Roster.pdf",
            defaultextension=".pdf",
            filetypes=[("PDF Documents", "*.pdf")]
        )
        if not dest:
            return

        gen = TimetablePDFGenerator(self.project)
        gen.export_duty_roster_pdf(dest)
        self._notify_export_success(dest)

    def _export_subjects_pdf(self):
        if not self._check_schedule():
            return
        dest = filedialog.asksaveasfilename(
            initialdir=self._get_export_dir(),
            initialfile="Subject_Schedules_Report.pdf",
            defaultextension=".pdf",
            filetypes=[("PDF Documents", "*.pdf")]
        )
        if not dest:
            return

        gen = TimetablePDFGenerator(self.project)
        gen.export_subject_schedules_pdf(dest)
        self._notify_export_success(dest)

    def _export_csv(self):
        if not self._check_schedule():
            return
        folder = filedialog.askdirectory(initialdir=self._get_export_dir(), title="Select Destination Folder for CSVs")
        if not folder:
            return

        csv_gen = TimetableSpreadsheetExporter(self.project)
        p1 = os.path.join(folder, "Master_Timetable.csv")
        p2 = os.path.join(folder, "Staff_Duty_Roster.csv")
        csv_gen.export_master_csv(p1)
        csv_gen.export_duty_roster_csv(p2)

        messagebox.showinfo("Export Complete", f"Exported CSV spreadsheets to:\n{folder}")

    def _check_schedule(self) -> bool:
        if not self.project.is_generated or not self.project.schedule:
            messagebox.showwarning("Warning", "Timetable has not been generated yet. Please generate the timetable on the Dashboard first.")
            return False
        return True

    def _notify_export_success(self, filepath: str):
        self.last_exported_file = filepath
        self.btn_open_file.config(state="normal")
        if messagebox.askyesno("PDF Exported Successfully!", f"Document saved:\n{filepath}\n\nWould you like to open it now?"):
            self._open_file(filepath)

    def _open_last_file(self):
        if self.last_exported_file and os.path.exists(self.last_exported_file):
            self._open_file(self.last_exported_file)

    def _open_export_dir(self):
        d = self._get_export_dir()
        if os.name == 'nt':
            os.startfile(d)
        else:
            subprocess.Popen(['xdg-open', d])

    def _open_file(self, filepath: str):
        if os.name == 'nt':
            os.startfile(filepath)
        else:
            subprocess.Popen(['xdg-open', filepath])

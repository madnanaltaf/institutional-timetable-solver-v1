"""
Professional Institutional PDF Timetable & Duty Roster Generator
Generates publication-ready PDF schedules for:
1. Teacher-wise timetables (individual or compiled faculty booklet)
2. Class & Section-wise timetables (with subject legend & room numbers)
3. Subject-wise schedules
4. Master institutional matrix timetable (panoramic overview)
5. Duty roster & invigilation allocation schedules
"""
import os
import datetime
from typing import Dict, List, Optional, Any

from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)

from models.timetable_data import TimetableProject
from models.lesson import ScheduledSlot
from models.section import Section
from models.teacher import Teacher
from models.subject import Subject

# Palette for PDF accents
PRIMARY_COLOR = colors.HexColor("#1E3A8A")     # Deep Navy
SECONDARY_COLOR = colors.HexColor("#0284C7")   # Bright Blue
HEADER_BG = colors.HexColor("#F1F5F9")         # Slate Light
BORDER_COLOR = colors.HexColor("#CBD5E1")      # Border Slate
TEXT_DARK = colors.HexColor("#0F172A")         # Deep Slate
TEXT_MUTED = colors.HexColor("#64748B")        # Muted Slate
BREAK_BG = colors.HexColor("#FEF3C7")          # Warm Yellow/Cream for Recess
BREAK_TEXT = colors.HexColor("#92400E")


class NumberedCanvas:
    """Canvas helper to draw running headers, footers and page numbers."""
    def __init__(self, *args, **kwargs):
        pass


class TimetablePDFGenerator:
    def __init__(self, project: TimetableProject):
        self.project = project
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        self.styles.add(ParagraphStyle(
            'InstHeader',
            fontName='Helvetica-Bold',
            fontSize=16,
            leading=20,
            textColor=PRIMARY_COLOR,
            alignment=1  # Center
        ))
        self.styles.add(ParagraphStyle(
            'InstSubHeader',
            fontName='Helvetica-Bold',
            fontSize=11,
            leading=14,
            textColor=SECONDARY_COLOR,
            alignment=1
        ))
        self.styles.add(ParagraphStyle(
            'DocMeta',
            fontName='Helvetica-Oblique',
            fontSize=8,
            leading=10,
            textColor=TEXT_MUTED,
            alignment=1
        ))
        self.styles.add(ParagraphStyle(
            'SectionTitle',
            fontName='Helvetica-Bold',
            fontSize=12,
            leading=15,
            textColor=PRIMARY_COLOR,
            spaceAfter=4
        ))
        self.styles.add(ParagraphStyle(
            'GridCellSubject',
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=TEXT_DARK,
            alignment=1
        ))
        self.styles.add(ParagraphStyle(
            'GridCellDetail',
            fontName='Helvetica',
            fontSize=7,
            leading=8,
            textColor=TEXT_MUTED,
            alignment=1
        ))
        self.styles.add(ParagraphStyle(
            'BreakCell',
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=BREAK_TEXT,
            alignment=1
        ))

    def _build_header_elements(self, doc_title: str, subtitle: str = "") -> List[Any]:
        elements = []
        inst = self.project.institution
        elements.append(Paragraph(inst.name.upper(), self.styles['InstHeader']))
        sub = f"{inst.academic_year} • {inst.term}"
        if subtitle:
            sub = f"{subtitle} | {sub}"
        elements.append(Paragraph(sub, self.styles['InstSubHeader']))
        meta_str = f"Document: {doc_title}  |  Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}  |  {inst.motto}"
        elements.append(Paragraph(meta_str, self.styles['DocMeta']))
        elements.append(Spacer(1, 8))
        elements.append(HRFlowable(width="100%", thickness=1, color=SECONDARY_COLOR, spaceAfter=8))
        return elements

    # ---------------------------------------------------------
    # 1. SECTION-WISE / CLASS-WISE TIMETABLES
    # ---------------------------------------------------------
    def export_section_timetables_pdf(self, output_path: str, target_section_id: Optional[str] = None):
        """
        Exports class/section timetables. If target_section_id is None, generates
        a multi-page booklet for all sections in the institution.
        """
        doc = SimpleDocTemplate(
            output_path,
            pagesize=landscape(A4),
            leftMargin=24,
            rightMargin=24,
            topMargin=24,
            bottomMargin=24
        )
        elements = []

        sections_to_export = [
            self.project.sections[target_section_id]
        ] if target_section_id and target_section_id in self.project.sections else list(self.project.sections.values())

        for idx, sec in enumerate(sections_to_export):
            if idx > 0:
                elements.append(PageBreak())

            incharge = self.project.teachers.get(sec.class_teacher_id)
            incharge_str = f"Class Teacher / Incharge: {incharge.name} ({incharge.code})" if incharge else "Class Teacher: Not Assigned"

            elements.extend(self._build_header_elements(
                doc_title=f"Class Timetable - {sec.display_name}",
                subtitle=f"Class: {sec.class_name} | Section: {sec.name} | Strength: {sec.student_count} | {incharge_str}"
            ))

            # Home room info
            home_room = self.project.classrooms.get(sec.home_room_id)
            home_str = f"Base Classroom: {home_room.name} ({home_room.building})" if home_room else ""
            if home_str:
                elements.append(Paragraph(home_str, self.styles['GridCellDetail']))
                elements.append(Spacer(1, 4))

            # Timetable Grid
            table = self._build_section_grid_table(sec.id)
            elements.append(table)
            elements.append(Spacer(1, 10))

            # Subject Legend / Teacher mapping
            legend = self._build_section_legend_table(sec.id)
            if legend:
                elements.append(Paragraph("Subject & Faculty Directory:", self.styles['SectionTitle']))
                elements.append(legend)

        doc.build(elements)

    def _build_section_grid_table(self, section_id: str) -> Table:
        days = list(self.project.institution.working_days)
        periods_count = self.project.institution.get_max_periods_any_day()
        break_after = self.project.institution.break_after_period

        # Columns: Period Label | Day 1 | Day 2 | ...
        header_row = ["Period / Time"]
        for day in days:
            day_p = self.project.institution.get_periods_for_day(day)
            lbl = f"{day}\n({day_p} Periods)" if day == "Friday" or day_p != self.project.institution.periods_per_day else day
            header_row.append(lbl)
        table_data = [header_row]

        # Fetch section slots
        slots = self.project.get_section_slots(section_id)

        for p in range(1, periods_count + 1):
            time_label = self.project.institution.get_period_label(p)
            row = [time_label]

            for day in days:
                day_max_p = self.project.institution.get_periods_for_day(day)
                if p > day_max_p:
                    row.append(Paragraph("<font color='#64748B'><i>— Early Dismissal —<br/><font size=6 color='#94A3B8'>[Jummah/Weekend]</font></i></font>", self.styles['GridCellDetail']))
                    continue

                # Find slot for this section at (day, p)
                matching = None
                for s in slots:
                    if s.day == day and s.period <= p < s.period + s.duration:
                        matching = s
                        break

                if matching:
                    sub = self.project.subjects.get(matching.subject_id)
                    teacher = self.project.teachers.get(matching.teacher_id)
                    room = self.project.classrooms.get(matching.room_id)

                    sub_name = sub.name if sub else matching.subject_id
                    t_name = teacher.name if teacher else matching.teacher_id
                    r_name = f"[{room.name}]" if room else ""
                    sync_tag = " • Synced Lab" if matching.sync_group_id else ""

                    cell_p = Paragraph(
                        f"<b>{sub_name}</b>{sync_tag}<br/>"
                        f"<font size=6 color='#475569'>{t_name} {r_name}</font>",
                        self.styles['GridCellSubject']
                    )
                    row.append(cell_p)
                else:
                    row.append(Paragraph("<font color='#94A3B8'>— Free / Study —</font>", self.styles['GridCellDetail']))

            table_data.append(row)

            # Insert Break Row if this is the break period
            if p == break_after and p < periods_count:
                break_row = ["RECESS / LUNCH"] + [Paragraph("<b>RECESS / CAMPUS BREAK</b>", self.styles['BreakCell']) for _ in days]
                table_data.append(break_row)

        # Table Styling
        col_widths = [85] + [(792 - 48 - 85) / len(days)] * len(days)
        t_style = [
            ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('BOX', (0, 0), (-1, -1), 1, PRIMARY_COLOR),
            ('BACKGROUND', (0, 0), (0, -1), HEADER_BG),
        ]

        # Highlight break row
        row_idx = 1
        for p in range(1, periods_count + 1):
            row_idx += 1
            if p == break_after and p < periods_count:
                t_style.append(('BACKGROUND', (0, row_idx - 1), (-1, row_idx - 1), BREAK_BG))
                row_idx += 1

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle(t_style))
        return table

    def _build_section_legend_table(self, section_id: str) -> Optional[Table]:
        lessons = [l for l in self.project.lessons.values() if l.section_id == section_id]
        if not lessons:
            return None

        data = [["Subject Code", "Subject Name", "Type", "Faculty Instructor", "Periods/Wk", "Location / Lab"]]
        for l in lessons:
            sub = self.project.subjects.get(l.subject_id)
            teacher = self.project.teachers.get(l.teacher_id)
            room = self.project.classrooms.get(l.room_id)

            sub_code = sub.code if sub else ""
            sub_name = sub.name if sub else l.subject_id
            sub_type = sub.subject_type if sub else "Theory"
            t_name = teacher.name if teacher else l.teacher_id
            r_name = room.name if room else (sub.default_room_type if sub else "Classroom")

            data.append([sub_code, sub_name, sub_type, t_name, str(l.periods_per_week), r_name])

        table = Table(data, colWidths=[65, 170, 75, 170, 65, 150])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), SECONDARY_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (4, 0), (4, -1), 'CENTER'),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('BOX', (0, 0), (-1, -1), 0.5, SECONDARY_COLOR),
        ]))
        return table

    # ---------------------------------------------------------
    # 2. TEACHER-WISE TIMETABLES & DUTY ROSTER
    # ---------------------------------------------------------
    def export_teacher_timetables_pdf(self, output_path: str, target_teacher_id: Optional[str] = None):
        """
        Exports teacher schedules including their teaching timetable and campus duty commitments.
        """
        doc = SimpleDocTemplate(
            output_path,
            pagesize=landscape(A4),
            leftMargin=24,
            rightMargin=24,
            topMargin=24,
            bottomMargin=24
        )
        elements = []

        teachers_to_export = [
            self.project.teachers[target_teacher_id]
        ] if target_teacher_id and target_teacher_id in self.project.teachers else list(self.project.teachers.values())

        for idx, teacher in enumerate(teachers_to_export):
            if idx > 0:
                elements.append(PageBreak())

            slots = self.project.get_teacher_slots(teacher.id)
            total_teaching_periods = sum(s.duration for s in slots)
            duties = self.project.get_teacher_duties(teacher.id)

            incharge_secs = [s.display_name for s in self.project.sections.values() if s.class_teacher_id == teacher.id]
            incharge_sub = f" | Class Incharge: {', '.join(incharge_secs)}" if incharge_secs else ""
            primary_sub = self.project.subjects.get(teacher.primary_subject_id)
            spec_str = f" | Specialist: {primary_sub.name} ({primary_sub.code})" if primary_sub else ""

            elements.extend(self._build_header_elements(
                doc_title=f"Faculty Timetable - {teacher.name} ({teacher.code})",
                subtitle=f"Load: {total_teaching_periods} periods/wk | Duties: {len(duties)}{spec_str}{incharge_sub}"
            ))

            # Timetable Grid
            table = self._build_teacher_grid_table(teacher.id)
            elements.append(table)
            elements.append(Spacer(1, 10))

            # Duties section
            if duties:
                elements.append(Paragraph("Assigned Institutional Duties & Invigilation:", self.styles['SectionTitle']))
                duty_table = self._build_teacher_duty_table(duties)
                elements.append(duty_table)

        doc.build(elements)

    def _build_teacher_grid_table(self, teacher_id: str) -> Table:
        days = list(self.project.institution.working_days)
        periods_count = self.project.institution.get_max_periods_any_day()
        break_after = self.project.institution.break_after_period

        header_row = ["Period / Time"]
        for day in days:
            day_p = self.project.institution.get_periods_for_day(day)
            lbl = f"{day}\n({day_p} Periods)" if day == "Friday" or day_p != self.project.institution.periods_per_day else day
            header_row.append(lbl)
        table_data = [header_row]
        slots = self.project.get_teacher_slots(teacher_id)
        teacher = self.project.teachers.get(teacher_id)

        for p in range(1, periods_count + 1):
            time_label = self.project.institution.get_period_label(p)
            row = [time_label]

            for day in days:
                day_max_p = self.project.institution.get_periods_for_day(day)
                if p > day_max_p:
                    row.append(Paragraph("<font color='#64748B'><i>— Early Dismissal —</i></font>", self.styles['GridCellDetail']))
                    continue

                # Check teacher unavailability
                if teacher and not teacher.is_available(day, p):
                    row.append(Paragraph("<font color='#EF4444'><b>[Unavailable]</b></font>", self.styles['GridCellDetail']))
                    continue

                matching = None
                for s in slots:
                    if s.day == day and s.period <= p < s.period + s.duration:
                        matching = s
                        break

                if matching:
                    sub = self.project.subjects.get(matching.subject_id)
                    sec = self.project.sections.get(matching.section_id)
                    room = self.project.classrooms.get(matching.room_id)

                    sub_name = sub.name if sub else matching.subject_id
                    sec_name = sec.display_name if sec else matching.section_id
                    r_name = f"[{room.name}]" if room else ""

                    cell_p = Paragraph(
                        f"<b>{sec_name}</b><br/>"
                        f"<font size=6.5 color='#1E40AF'>{sub_name}</font><br/>"
                        f"<font size=6 color='#64748B'>{r_name}</font>",
                        self.styles['GridCellSubject']
                    )
                    row.append(cell_p)
                else:
                    row.append(Paragraph("<font color='#94A3B8'>Free Period</font>", self.styles['GridCellDetail']))

            table_data.append(row)

            # Insert Break Row
            if p == break_after and p < periods_count:
                break_row = ["RECESS"] + [Paragraph("<b>RECESS / CAMPUS BREAK</b>", self.styles['BreakCell']) for _ in days]
                table_data.append(break_row)

        col_widths = [85] + [(792 - 48 - 85) / len(days)] * len(days)
        t_style = [
            ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('BOX', (0, 0), (-1, -1), 1, PRIMARY_COLOR),
            ('BACKGROUND', (0, 0), (0, -1), HEADER_BG),
        ]

        row_idx = 1
        for p in range(1, periods_count + 1):
            row_idx += 1
            if p == break_after and p < periods_count:
                t_style.append(('BACKGROUND', (0, row_idx - 1), (-1, row_idx - 1), BREAK_BG))
                row_idx += 1

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle(t_style))
        return table

    def _build_teacher_duty_table(self, duties: List[Any]) -> Table:
        data = [["Day", "Time Slot / Period", "Duty Assignment", "Campus Location"]]
        for d in duties:
            p_str = d.time_label or (f"Period {d.period}" if d.period > 0 else "Morning Assembly / Gate")
            data.append([d.day, p_str, d.duty_name, d.location])

        table = Table(data, colWidths=[100, 140, 260, 240])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), SECONDARY_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('BOX', (0, 0), (-1, -1), 0.5, SECONDARY_COLOR),
        ]))
        return table

    # ---------------------------------------------------------
    # 3. SUBJECT-WISE SCHEDULE TIMETABLE
    # ---------------------------------------------------------
    def export_subject_schedules_pdf(self, output_path: str):
        """
        Generates comprehensive timetable report organized by subject.
        """
        doc = SimpleDocTemplate(
            output_path,
            pagesize=landscape(A4),
            leftMargin=24,
            rightMargin=24,
            topMargin=24,
            bottomMargin=24
        )
        elements = []

        elements.extend(self._build_header_elements(
            doc_title="Subject-Wise Curriculum Schedule",
            subtitle="Master Subject Allocations, Labs, Faculty & Time Slots"
        ))

        for sub_id, sub in self.project.subjects.items():
            slots = self.project.get_subject_slots(sub_id)
            if not slots:
                continue

            elements.append(Paragraph(
                f"<b>{sub.name} ({sub.code})</b> &nbsp;&nbsp; "
                f"<font size=8 color='#64748B'>Type: {sub.subject_type} | Lab Required: {'Yes' if sub.requires_lab else 'No'} | Weekly Slots: {len(slots)}</font>",
                self.styles['SectionTitle']
            ))

            data = [["Day", "Period / Time", "Class & Section", "Teacher", "Room / Laboratory", "Type"]]
            # Sort slots chronologically
            days_order = {d: i for i, d in enumerate(self.project.institution.working_days)}
            slots_sorted = sorted(slots, key=lambda s: (days_order.get(s.day, 99), s.period))

            for s in slots_sorted:
                sec = self.project.sections.get(s.section_id)
                teacher = self.project.teachers.get(s.teacher_id)
                room = self.project.classrooms.get(s.room_id)
                time_lbl = self.project.institution.get_period_label(s.period)
                dur_lbl = f"{s.duration} periods" if s.duration > 1 else "1 period"

                data.append([
                    s.day,
                    time_lbl,
                    sec.display_name if sec else s.section_id,
                    teacher.name if teacher else s.teacher_id,
                    room.name if room else "Classroom",
                    f"{dur_lbl} ({'Sync Lab' if s.sync_group_id else 'Regular'})"
                ])

            table = Table(data, colWidths=[80, 110, 160, 160, 130, 100])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ('BOX', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 10))

        doc.build(elements)

    # ---------------------------------------------------------
    # 4. MASTER INSTITUTIONAL TIMETABLE
    # ---------------------------------------------------------
    def export_master_timetable_pdf(self, output_path: str):
        """
        Exports the master institution matrix with all sections and periods.
        """
        doc = SimpleDocTemplate(
            output_path,
            pagesize=landscape(A4),
            leftMargin=20,
            rightMargin=20,
            topMargin=20,
            bottomMargin=20
        )
        elements = []

        elements.extend(self._build_header_elements(
            doc_title="Master Institutional Schedule Matrix",
            subtitle=f"All Classes & Sections Overview ({len(self.project.sections)} Sections, {len(self.project.teachers)} Faculty)"
        ))

        days = list(self.project.institution.working_days)
        sections = list(self.project.sections.values())

        for day in days:
            day_periods = self.project.institution.get_periods_for_day(day)
            dismissal_note = f" — Early Dismissal after Period {day_periods}" if day_periods < self.project.institution.periods_per_day else ""
            elements.append(Paragraph(f"<b>DAY: {day.upper()}{dismissal_note}</b>", self.styles['SectionTitle']))

            header_row = ["Class / Section"] + [f"Period {p}" for p in range(1, day_periods + 1)]
            table_data = [header_row]

            for sec in sections:
                row = [sec.display_name]
                for p in range(1, day_periods + 1):
                    slot = self.project.get_slot_at(day, p, sec.id)
                    if slot:
                        sub = self.project.subjects.get(slot.subject_id)
                        teacher = self.project.teachers.get(slot.teacher_id)
                        room = self.project.classrooms.get(slot.room_id)

                        sub_code = sub.code if sub else slot.subject_id
                        t_code = teacher.code if teacher else ""
                        r_name = room.name if room else ""

                        cell_text = f"<b>{sub_code}</b><br/><font size=5.5 color='#475569'>{t_code} {r_name}</font>"
                        row.append(Paragraph(cell_text, self.styles['GridCellSubject']))
                    else:
                        row.append(Paragraph("<font size=6 color='#CBD5E1'>—</font>", self.styles['GridCellDetail']))
                table_data.append(row)

            col_w = [110] + [(792 - 40 - 110) / day_periods] * day_periods
            table = Table(table_data, colWidths=col_w)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ('BOX', (0, 0), (-1, -1), 1, PRIMARY_COLOR),
                ('BACKGROUND', (0, 1), (0, -1), HEADER_BG),
            ]))
            elements.append(table)
            elements.append(Spacer(1, 14))

        doc.build(elements)

    # ---------------------------------------------------------
    # 5. DUTY ROSTER & INVIGILATION ALLOCATION PDF
    # ---------------------------------------------------------
    def export_duty_roster_pdf(self, output_path: str):
        """
        Exports the complete staff duty roster, invigilation matrix, and fairness distribution.
        """
        doc = SimpleDocTemplate(
            output_path,
            pagesize=landscape(A4),
            leftMargin=24,
            rightMargin=24,
            topMargin=24,
            bottomMargin=24
        )
        elements = []

        elements.extend(self._build_header_elements(
            doc_title="Institutional Staff Duty Roster & Invigilation Schedule",
            subtitle=f"Fair-Share Duty Balancing ({len(self.project.duty_assignments)} Total Duty Assignments)"
        ))

        # Duty assignments table
        elements.append(Paragraph("Weekly Duty Assignments Roster:", self.styles['SectionTitle']))
        data = [["Day", "Slot / Time", "Duty Description", "Location", "Assigned Faculty Member"]]

        days_order = {d: i for i, d in enumerate(self.project.institution.working_days)}
        duties_sorted = sorted(self.project.duty_assignments, key=lambda d: (days_order.get(d.day, 99), d.period))

        for d in duties_sorted:
            time_lbl = d.time_label or (f"Period {d.period}" if d.period > 0 else "Morning Supervision")
            data.append([d.day, time_lbl, d.duty_name, d.location, f"<b>{d.teacher_name}</b>"])

        duty_table = Table(data, colWidths=[85, 120, 220, 170, 150])
        duty_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('BOX', (0, 0), (-1, -1), 1, PRIMARY_COLOR),
        ]))
        elements.append(duty_table)
        elements.append(Spacer(1, 16))

        # Teacher Duty Load Summary (Fairness Verification)
        elements.append(Paragraph("Faculty Duty Load Balance & Fairness Summary:", self.styles['SectionTitle']))
        summary_data = [["Teacher Code", "Teacher Name", "Total Assigned Duties", "Weekly Teaching Load", "Fairness Status"]]

        teacher_duty_counts: Dict[str, int] = {}
        for d in self.project.duty_assignments:
            teacher_duty_counts[d.teacher_id] = teacher_duty_counts.get(d.teacher_id, 0) + 1

        for t_id, teacher in self.project.teachers.items():
            count = teacher_duty_counts.get(t_id, 0)
            slots = self.project.get_teacher_slots(t_id)
            teach_load = sum(s.duration for s in slots)
            summary_data.append([
                teacher.code,
                teacher.name,
                f"{count} duties",
                f"{teach_load} periods",
                "Balanced (Optimal)" if 1 <= count <= 3 else "Assigned"
            ])

        sum_table = Table(summary_data, colWidths=[90, 220, 140, 140, 150])
        sum_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), SECONDARY_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 0), (3, -1), 'CENTER'),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('BOX', (0, 0), (-1, -1), 0.5, SECONDARY_COLOR),
        ]))
        elements.append(sum_table)

        doc.build(elements)

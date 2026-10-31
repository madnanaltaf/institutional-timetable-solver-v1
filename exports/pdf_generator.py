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

    def _compute_grid_col_widths(self, periods_count: int, break_after: int, target_width: float = 776.0) -> List[float]:
        """
        Dynamically computes exact column widths so the table fits landscape A4
        with clean, guaranteed margins on both left and right (never overflows or clips).
        """
        w_day = 66.0
        has_break = (0 < break_after < periods_count)
        w_break = 38.0 if has_break else 0.0

        remaining_w = target_width - w_day - w_break
        w_period = remaining_w / max(1, periods_count)

        if has_break:
            return [w_day] + [w_period] * break_after + [w_break] + [w_period] * (periods_count - break_after)
        return [w_day] + [w_period] * periods_count

    def _compute_grid_row_heights(self, n_days: int) -> List[float]:
        """
        Dynamically computes row heights so that whether 5, 6, or 7 days are active,
        the entire timetable grid fits cleanly on a single Landscape A4 page.
        """
        header_h = 28.0
        row_h = min(62.0, max(42.0, 330.0 / max(1, n_days)))
        return [header_h] + [row_h] * n_days

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
            leftMargin=30,
            rightMargin=30,
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

            # Timetable Grid (Days by row, Periods by column)
            table = self._build_section_grid_table(sec.id)
            elements.append(table)
            # "below data not needed": only show class export with only timetable

        doc.build(elements)

    def _get_period_time(self, p: int) -> str:
        for pt in self.project.institution.period_times:
            if pt.period_num == p:
                return f"{pt.start_time} - {pt.end_time}"
        return ""

    def _build_section_grid_table(self, section_id: str) -> Table:
        days = list(self.project.institution.working_days)
        periods_count = self.project.institution.get_max_periods_any_day()
        break_after = self.project.institution.break_after_period
        has_break = (0 < break_after < periods_count)
        sec = self.project.sections.get(section_id)

        # Columns: Day / Timing | Period 1 .. 4 | RECESS | Period 5 .. N
        header_row = [Paragraph("<b>Day / Timing</b>", self.styles['GridCellSubject'])]
        limit_p1 = break_after if has_break else periods_count
        for p in range(1, limit_p1 + 1):
            t_str = self._get_period_time(p)
            lbl = f"<b>Period {p}</b><br/><font size=5.5 color='#64748B'>{t_str}</font>"
            header_row.append(Paragraph(lbl, self.styles['GridCellSubject']))

        if has_break:
            header_row.append(Paragraph("<b>RECESS</b><br/><font size=5.5 color='#92400E'>11:00-11:30</font>", self.styles['BreakCell']))
            for p in range(break_after + 1, periods_count + 1):
                t_str = self._get_period_time(p)
                lbl = f"<b>Period {p}</b><br/><font size=5.5 color='#64748B'>{t_str}</font>"
                header_row.append(Paragraph(lbl, self.styles['GridCellSubject']))

        table_data = [header_row]
        slots = self.project.get_section_slots(section_id)

        col_widths = self._compute_grid_col_widths(periods_count, break_after if has_break else 0)
        row_heights = self._compute_grid_row_heights(len(days))
        total_cols = len(col_widths)

        # Responsive cell styling
        sub_fs = 6.8 if periods_count >= 8 or len(days) >= 6 else 7.5
        tea_fs = 5.8 if periods_count >= 8 or len(days) >= 6 else 6.5
        rm_fs = 5.4 if periods_count >= 8 or len(days) >= 6 else 6.0

        t_style = [
            ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('BOX', (0, 0), (-1, -1), 1.5, PRIMARY_COLOR),
            ('BACKGROUND', (0, 1), (0, -1), HEADER_BG),
        ]
        if has_break:
            recess_col_idx = break_after + 1
            t_style.append(('BACKGROUND', (recess_col_idx, 0), (recess_col_idx, -1), BREAK_BG))
            t_style.append(('TEXTCOLOR', (recess_col_idx, 0), (recess_col_idx, -1), BREAK_TEXT))

        for r_idx, day in enumerate(days, start=1):
            day_max_p = self.project.institution.get_periods_for_day(day)
            if day_max_p < periods_count:
                day_lbl = Paragraph(f"<b>{day}</b><br/><font size=5.5 color='#0284C7'>[{day_max_p} Periods]</font>", self.styles['GridCellSubject'])
            else:
                day_lbl = Paragraph(f"<b>{day}</b>", self.styles['GridCellSubject'])

            row = [day_lbl]

            # Periods 1 to break_after (or all periods if no break)
            for p in range(1, limit_p1 + 1):
                if p > day_max_p:
                    row.append(Paragraph("<font size=6 color='#64748B'><i>— Dismissed —</i></font>", self.styles['GridCellDetail']))
                    continue

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
                    t_str = f"{teacher.name} ({teacher.code})" if teacher else matching.teacher_id
                    r_str = f"[{room.name}]" if room else ""
                    is_incharge = (sec and sec.class_teacher_id == matching.teacher_id)
                    badge = " ⭐" if is_incharge else ""
                    sync_tag = self._slot_tag(matching)

                    cell_p = Paragraph(
                        f"<font size={sub_fs} color='#0F172A'><b>{sub_name}</b>{sync_tag}</font><br/>"
                        f"<font size={tea_fs} color='#1E3A8A'>{t_str}{badge}</font><br/>"
                        f"<font size={rm_fs} color='#64748B'>{r_str}</font>",
                        self.styles['GridCellSubject']
                    )
                    row.append(cell_p)
                else:
                    row.append(Paragraph("<font size=6 color='#94A3B8'>— Free —</font>", self.styles['GridCellDetail']))

            if has_break:
                # Recess Column
                row.append(Paragraph("<b>RECESS<br/>BREAK</b>", self.styles['BreakCell']))

                # Periods after break (break_after + 1 to periods_count)
                if day_max_p <= break_after:
                    dismiss_start_col = break_after + 2
                    dismiss_end_col = total_cols - 1
                    row.append(Paragraph("<font color='#64748B'><i>— Early Dismissal —<br/><font size=5.5 color='#94A3B8'>[Jummah Prayer & Weekend]</font></i></font>", self.styles['GridCellDetail']))
                    for _ in range(dismiss_start_col, dismiss_end_col):
                        row.append("")
                    t_style.append(('SPAN', (dismiss_start_col, r_idx), (dismiss_end_col, r_idx)))
                    t_style.append(('BACKGROUND', (dismiss_start_col, r_idx), (dismiss_end_col, r_idx), colors.HexColor("#F8FAFC")))
                    t_style.append(('ALIGN', (dismiss_start_col, r_idx), (dismiss_end_col, r_idx), 'CENTER'))
                    t_style.append(('VALIGN', (dismiss_start_col, r_idx), (dismiss_end_col, r_idx), 'MIDDLE'))
                else:
                    for p in range(break_after + 1, periods_count + 1):
                        if p > day_max_p:
                            row.append(Paragraph("<font size=6 color='#64748B'><i>— Dismissed —</i></font>", self.styles['GridCellDetail']))
                            continue

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
                            t_str = f"{teacher.name} ({teacher.code})" if teacher else matching.teacher_id
                            r_str = f"[{room.name}]" if room else ""
                            is_incharge = (sec and sec.class_teacher_id == matching.teacher_id)
                            badge = " ⭐" if is_incharge else ""
                            sync_tag = self._slot_tag(matching)

                            cell_p = Paragraph(
                                f"<font size={sub_fs} color='#0F172A'><b>{sub_name}</b>{sync_tag}</font><br/>"
                                f"<font size={tea_fs} color='#1E3A8A'>{t_str}{badge}</font><br/>"
                                f"<font size={rm_fs} color='#64748B'>{r_str}</font>",
                                self.styles['GridCellSubject']
                            )
                            row.append(cell_p)
                        else:
                            row.append(Paragraph("<font size=6 color='#94A3B8'>— Free —</font>", self.styles['GridCellDetail']))

            table_data.append(row)

        table = Table(table_data, colWidths=col_widths, rowHeights=row_heights, repeatRows=1)
        table.setStyle(TableStyle(t_style))
        return table

    @staticmethod
    def _slot_tag(slot: Any) -> str:
        tags = []
        if getattr(slot, "sync_group_id", ""):
            tags.append("Paired")
        if getattr(slot, "combined_group_id", ""):
            tags.append("All Sections")
        return f" • {' + '.join(tags)}" if tags else ""

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
            leftMargin=30,
            rightMargin=30,
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
        has_break = (0 < break_after < periods_count)
        teacher = self.project.teachers.get(teacher_id)
        slots = self.project.get_teacher_slots(teacher_id)

        # Header row
        header_row = [Paragraph("<b>Day / Timing</b>", self.styles['GridCellSubject'])]
        limit_p1 = break_after if has_break else periods_count
        for p in range(1, limit_p1 + 1):
            t_str = self._get_period_time(p)
            lbl = f"<b>Period {p}</b><br/><font size=5.5 color='#64748B'>{t_str}</font>"
            header_row.append(Paragraph(lbl, self.styles['GridCellSubject']))

        if has_break:
            header_row.append(Paragraph("<b>RECESS</b><br/><font size=5.5 color='#92400E'>11:00-11:30</font>", self.styles['BreakCell']))
            for p in range(break_after + 1, periods_count + 1):
                t_str = self._get_period_time(p)
                lbl = f"<b>Period {p}</b><br/><font size=5.5 color='#64748B'>{t_str}</font>"
                header_row.append(Paragraph(lbl, self.styles['GridCellSubject']))

        table_data = [header_row]
        col_widths = self._compute_grid_col_widths(periods_count, break_after if has_break else 0)
        row_heights = self._compute_grid_row_heights(len(days))
        total_cols = len(col_widths)

        # Responsive cell styling
        sub_fs = 6.8 if periods_count >= 8 or len(days) >= 6 else 7.5
        tea_fs = 5.8 if periods_count >= 8 or len(days) >= 6 else 6.5
        rm_fs = 5.4 if periods_count >= 8 or len(days) >= 6 else 6.0

        t_style = [
            ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('BOX', (0, 0), (-1, -1), 1.5, PRIMARY_COLOR),
            ('BACKGROUND', (0, 1), (0, -1), HEADER_BG),
        ]
        if has_break:
            recess_col_idx = break_after + 1
            t_style.append(('BACKGROUND', (recess_col_idx, 0), (recess_col_idx, -1), BREAK_BG))
            t_style.append(('TEXTCOLOR', (recess_col_idx, 0), (recess_col_idx, -1), BREAK_TEXT))

        for r_idx, day in enumerate(days, start=1):
            day_max_p = self.project.institution.get_periods_for_day(day)
            if day_max_p < periods_count:
                day_lbl = Paragraph(f"<b>{day}</b><br/><font size=5.5 color='#0284C7'>[{day_max_p} Periods]</font>", self.styles['GridCellSubject'])
            else:
                day_lbl = Paragraph(f"<b>{day}</b>", self.styles['GridCellSubject'])

            row = [day_lbl]

            # Periods 1 to break_after (or all periods)
            for p in range(1, limit_p1 + 1):
                if p > day_max_p:
                    row.append(Paragraph("<font size=6 color='#64748B'><i>— Dismissed —</i></font>", self.styles['GridCellDetail']))
                    continue

                if teacher and not teacher.is_available(day, p):
                    row.append(Paragraph("<font size=6 color='#EF4444'><b>[Blocked]</b></font>", self.styles['GridCellDetail']))
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
                    sec_name = sec.display_name if sec else matching.section_id
                    sub_name = sub.name if sub else matching.subject_id
                    r_name = f"[{room.name}]" if room else ""
                    sync_tag = self._slot_tag(matching)

                    cell_p = Paragraph(
                        f"<font size={sub_fs} color='#0F172A'><b>{sec_name}</b>{sync_tag}</font><br/>"
                        f"<font size={tea_fs} color='#1E3A8A'>{sub_name}</font><br/>"
                        f"<font size={rm_fs} color='#64748B'>{r_name}</font>",
                        self.styles['GridCellSubject']
                    )
                    row.append(cell_p)
                else:
                    row.append(Paragraph("<font size=6 color='#94A3B8'>Free</font>", self.styles['GridCellDetail']))

            if has_break:
                # Recess Column
                row.append(Paragraph("<b>RECESS<br/>BREAK</b>", self.styles['BreakCell']))

                # Periods after break (break_after + 1 to periods_count)
                if day_max_p <= break_after:
                    dismiss_start_col = break_after + 2
                    dismiss_end_col = total_cols - 1
                    row.append(Paragraph("<font color='#64748B'><i>— Early Dismissal —<br/><font size=5.5 color='#94A3B8'>[Jummah Prayer & Weekend]</font></i></font>", self.styles['GridCellDetail']))
                    for _ in range(dismiss_start_col, dismiss_end_col):
                        row.append("")
                    t_style.append(('SPAN', (dismiss_start_col, r_idx), (dismiss_end_col, r_idx)))
                    t_style.append(('BACKGROUND', (dismiss_start_col, r_idx), (dismiss_end_col, r_idx), colors.HexColor("#F8FAFC")))
                    t_style.append(('ALIGN', (dismiss_start_col, r_idx), (dismiss_end_col, r_idx), 'CENTER'))
                    t_style.append(('VALIGN', (dismiss_start_col, r_idx), (dismiss_end_col, r_idx), 'MIDDLE'))
                else:
                    for p in range(break_after + 1, periods_count + 1):
                        if p > day_max_p:
                            row.append(Paragraph("<font size=6 color='#64748B'><i>— Dismissed —</i></font>", self.styles['GridCellDetail']))
                            continue

                        if teacher and not teacher.is_available(day, p):
                            row.append(Paragraph("<font size=6 color='#EF4444'><b>[Blocked]</b></font>", self.styles['GridCellDetail']))
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
                            sec_name = sec.display_name if sec else matching.section_id
                            sub_name = sub.name if sub else matching.subject_id
                            r_name = f"[{room.name}]" if room else ""
                            sync_tag = self._slot_tag(matching)

                            cell_p = Paragraph(
                                f"<font size={sub_fs} color='#0F172A'><b>{sec_name}</b>{sync_tag}</font><br/>"
                                f"<font size={tea_fs} color='#1E3A8A'>{sub_name}</font><br/>"
                                f"<font size={rm_fs} color='#64748B'>{r_name}</font>",
                                self.styles['GridCellSubject']
                            )
                            row.append(cell_p)
                        else:
                            row.append(Paragraph("<font size=6 color='#94A3B8'>Free</font>", self.styles['GridCellDetail']))

            table_data.append(row)

        table = Table(table_data, colWidths=col_widths, rowHeights=row_heights, repeatRows=1)
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
            leftMargin=30,
            rightMargin=30,
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
                    f"{dur_lbl} ({'All Sections' if s.combined_group_id else ('Sync Lab' if s.sync_group_id else 'Regular')})"
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
    # 4. MASTER INSTITUTIONAL MATRIX TIMETABLES (BY DAY)
    # ---------------------------------------------------------
    def export_master_timetable_pdf(self, output_path: str):
        """
        Exports the master institution classes & sections matrix by day (1 page per day).
        Fits cleanly on landscape A4 with guaranteed margins.
        """
        doc = SimpleDocTemplate(
            output_path,
            pagesize=landscape(A4),
            leftMargin=30,
            rightMargin=30,
            topMargin=24,
            bottomMargin=24
        )
        elements = []
        days = list(self.project.institution.working_days)
        sections = list(self.project.sections.values())
        break_after = self.project.institution.break_after_period

        for d_idx, day in enumerate(days):
            if d_idx > 0:
                elements.append(PageBreak())

            day_periods = self.project.institution.get_periods_for_day(day)
            has_break = (0 < break_after < day_periods)
            dismissal_note = f" (Early Dismissal after Period {day_periods})" if day_periods < self.project.institution.periods_per_day else ""

            elements.extend(self._build_header_elements(
                doc_title=f"Master Timetable Matrix — {day.upper()}{dismissal_note}",
                subtitle=f"Daily Classes & Sections Overview ({len(sections)} Sections) • {self.project.institution.academic_year}"
            ))

            w_class = 92.0
            w_break = 38.0 if has_break else 0.0
            remaining_w = 776.0 - w_class - w_break
            w_period = remaining_w / max(1, day_periods)

            header_row = [Paragraph("<b>Class / Section</b>", self.styles['GridCellSubject'])]
            col_w = [w_class]

            for p in range(1, break_after + 1 if has_break else day_periods + 1):
                t_str = self._get_period_time(p)
                lbl = f"<b>Period {p}</b><br/><font size=5.5 color='#64748B'>{t_str}</font>"
                header_row.append(Paragraph(lbl, self.styles['GridCellSubject']))
                col_w.append(w_period)

            if has_break:
                header_row.append(Paragraph("<b>RECESS</b><br/><font size=5.5 color='#92400E'>11:00</font>", self.styles['BreakCell']))
                col_w.append(w_break)
                for p in range(break_after + 1, day_periods + 1):
                    t_str = self._get_period_time(p)
                    lbl = f"<b>Period {p}</b><br/><font size=5.5 color='#64748B'>{t_str}</font>"
                    header_row.append(Paragraph(lbl, self.styles['GridCellSubject']))
                    col_w.append(w_period)

            table_data = [header_row]
            n_sec = len(sections)
            r_height = min(20.0, max(15.0, 360.0 / max(1, n_sec)))
            row_heights = [24.0] + [r_height] * n_sec

            t_style = [
                ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ('BOX', (0, 0), (-1, -1), 1.2, PRIMARY_COLOR),
                ('BACKGROUND', (0, 1), (0, -1), HEADER_BG),
            ]
            if has_break:
                recess_col_idx = break_after + 1
                t_style.append(('BACKGROUND', (recess_col_idx, 0), (recess_col_idx, -1), BREAK_BG))
                t_style.append(('TEXTCOLOR', (recess_col_idx, 0), (recess_col_idx, -1), BREAK_TEXT))

            for sec in sections:
                row = [Paragraph(f"<b>{sec.display_name}</b>", self.styles['GridCellSubject'])]
                for p in range(1, break_after + 1 if has_break else day_periods + 1):
                    slot = self.project.get_slot_at(day, p, sec.id)
                    if slot:
                        sub = self.project.subjects.get(slot.subject_id)
                        teacher = self.project.teachers.get(slot.teacher_id)
                        room = self.project.classrooms.get(slot.room_id)
                        sub_code = sub.code if sub else slot.subject_id
                        t_code = teacher.code if teacher else ""
                        r_name = room.name if room else ""
                        row.append(Paragraph(
                            f"<font size=6.5 color='#0F172A'><b>{sub_code}</b></font> "
                            f"<font size=5.5 color='#1E3A8A'>{t_code}</font><br/>"
                            f"<font size=5 color='#64748B'>{r_name}</font>",
                            self.styles['GridCellSubject']
                        ))
                    else:
                        row.append(Paragraph("<font size=6 color='#CBD5E1'>—</font>", self.styles['GridCellDetail']))

                if has_break:
                    row.append(Paragraph("<b>RECESS</b>", self.styles['BreakCell']))
                    for p in range(break_after + 1, day_periods + 1):
                        slot = self.project.get_slot_at(day, p, sec.id)
                        if slot:
                            sub = self.project.subjects.get(slot.subject_id)
                            teacher = self.project.teachers.get(slot.teacher_id)
                            room = self.project.classrooms.get(slot.room_id)
                            sub_code = sub.code if sub else slot.subject_id
                            t_code = teacher.code if teacher else ""
                            r_name = room.name if room else ""
                            row.append(Paragraph(
                                f"<font size=6.5 color='#0F172A'><b>{sub_code}</b></font> "
                                f"<font size=5.5 color='#1E3A8A'>{t_code}</font><br/>"
                                f"<font size=5 color='#64748B'>{r_name}</font>",
                                self.styles['GridCellSubject']
                            ))
                        else:
                            row.append(Paragraph("<font size=6 color='#CBD5E1'>—</font>", self.styles['GridCellDetail']))

                table_data.append(row)

            table = Table(table_data, colWidths=col_w, rowHeights=row_heights, repeatRows=1)
            table.setStyle(TableStyle(t_style))
            elements.append(table)

        doc.build(elements)

    def export_master_sections_matrix_by_day_pdf(self, output_path: str):
        """Dedicated alias for day-by-day class sections matrix booklet."""
        return self.export_master_timetable_pdf(output_path)

    def export_master_faculty_matrix_by_day_pdf(self, output_path: str):
        """
        Exports the master faculty schedule & substitution matrix by day (1 page per day).
        Shows where every teacher is stationed for every period, who has duty, and who is available.
        """
        doc = SimpleDocTemplate(
            output_path,
            pagesize=landscape(A4),
            leftMargin=30,
            rightMargin=30,
            topMargin=24,
            bottomMargin=24
        )
        elements = []
        days = list(self.project.institution.working_days)
        teachers = list(self.project.teachers.values())
        break_after = self.project.institution.break_after_period

        for d_idx, day in enumerate(days):
            if d_idx > 0:
                elements.append(PageBreak())

            day_periods = self.project.institution.get_periods_for_day(day)
            has_break = (0 < break_after < day_periods)
            dismissal_note = f" (Early Dismissal after Period {day_periods})" if day_periods < self.project.institution.periods_per_day else ""

            elements.extend(self._build_header_elements(
                doc_title=f"Master Faculty Schedule Matrix — {day.upper()}{dismissal_note}",
                subtitle=f"Daily Faculty Allocations, Duties & Availability ({len(teachers)} Faculty) • {self.project.institution.academic_year}"
            ))

            w_teacher = 110.0
            w_break = 38.0 if has_break else 0.0
            remaining_w = 776.0 - w_teacher - w_break
            w_period = remaining_w / max(1, day_periods)

            header_row = [Paragraph("<b>Faculty Member</b>", self.styles['GridCellSubject'])]
            col_w = [w_teacher]

            for p in range(1, break_after + 1 if has_break else day_periods + 1):
                t_str = self._get_period_time(p)
                lbl = f"<b>Period {p}</b><br/><font size=5.5 color='#64748B'>{t_str}</font>"
                header_row.append(Paragraph(lbl, self.styles['GridCellSubject']))
                col_w.append(w_period)

            if has_break:
                header_row.append(Paragraph("<b>RECESS</b><br/><font size=5.5 color='#92400E'>11:00</font>", self.styles['BreakCell']))
                col_w.append(w_break)
                for p in range(break_after + 1, day_periods + 1):
                    t_str = self._get_period_time(p)
                    lbl = f"<b>Period {p}</b><br/><font size=5.5 color='#64748B'>{t_str}</font>"
                    header_row.append(Paragraph(lbl, self.styles['GridCellSubject']))
                    col_w.append(w_period)

            table_data = [header_row]
            t_style = [
                ('BACKGROUND', (0, 0), (-1, 0), SECONDARY_COLOR),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ('BOX', (0, 0), (-1, -1), 1.2, SECONDARY_COLOR),
                ('BACKGROUND', (0, 1), (0, -1), HEADER_BG),
            ]
            if has_break:
                recess_col_idx = break_after + 1
                t_style.append(('BACKGROUND', (recess_col_idx, 0), (recess_col_idx, -1), BREAK_BG))
                t_style.append(('TEXTCOLOR', (recess_col_idx, 0), (recess_col_idx, -1), BREAK_TEXT))

            for t in teachers:
                sub_spec = self.project.subjects.get(t.primary_subject_id)
                spec_code = sub_spec.code if sub_spec else ""
                t_label = f"<b>{t.name} ({t.code})</b>"
                if spec_code:
                    t_label += f"<br/><font size=5.5 color='#64748B'>{spec_code} Specialist</font>"
                row = [Paragraph(t_label, self.styles['GridCellSubject'])]

                for p in range(1, break_after + 1 if has_break else day_periods + 1):
                    if not t.is_available(day, p):
                        row.append(Paragraph("<font size=5.5 color='#EF4444'>[Blocked]</font>", self.styles['GridCellDetail']))
                        continue

                    slot = self.project.get_teacher_slot_at(day, p, t.id)
                    if slot:
                        sec = self.project.sections.get(slot.section_id)
                        sub = self.project.subjects.get(slot.subject_id)
                        room = self.project.classrooms.get(slot.room_id)
                        sec_str = sec.name if sec else slot.section_id
                        sub_c = sub.code if sub else ""
                        r_c = f"[{room.name}]" if room else ""
                        row.append(Paragraph(
                            f"<font size=6 color='#0F172A'><b>{sec_str}</b></font> <font size=5.5 color='#1E3A8A'>{sub_c}</font><br/>"
                            f"<font size=5 color='#64748B'>{r_c}</font>",
                            self.styles['GridCellSubject']
                        ))
                    else:
                        duty = self.project.get_teacher_duty_at(day, p, t.id)
                        if duty:
                            row.append(Paragraph(f"<font size=5.5 color='#D97706'><b>🛡️ {duty.duty_name}</b></font>", self.styles['GridCellSubject']))
                        else:
                            row.append(Paragraph("<font size=5.5 color='#10B981'><b>Available</b></font>", self.styles['GridCellDetail']))

                if has_break:
                    # Check recess duty
                    recess_duty = self.project.get_teacher_duty_at(day, 0, t.id)
                    if recess_duty and "Recess" in recess_duty.duty_name:
                        row.append(Paragraph(f"<font size=5.5 color='#92400E'><b>🛡️ {recess_duty.duty_name}</b></font>", self.styles['BreakCell']))
                    else:
                        row.append(Paragraph("<b>RECESS</b>", self.styles['BreakCell']))

                    for p in range(break_after + 1, day_periods + 1):
                        if not t.is_available(day, p):
                            row.append(Paragraph("<font size=5.5 color='#EF4444'>[Blocked]</font>", self.styles['GridCellDetail']))
                            continue

                        slot = self.project.get_teacher_slot_at(day, p, t.id)
                        if slot:
                            sec = self.project.sections.get(slot.section_id)
                            sub = self.project.subjects.get(slot.subject_id)
                            room = self.project.classrooms.get(slot.room_id)
                            sec_str = sec.name if sec else slot.section_id
                            sub_c = sub.code if sub else ""
                            r_c = f"[{room.name}]" if room else ""
                            row.append(Paragraph(
                                f"<font size=6 color='#0F172A'><b>{sec_str}</b></font> <font size=5.5 color='#1E3A8A'>{sub_c}</font><br/>"
                                f"<font size=5 color='#64748B'>{r_c}</font>",
                                self.styles['GridCellSubject']
                            ))
                        else:
                            duty = self.project.get_teacher_duty_at(day, p, t.id)
                            if duty:
                                row.append(Paragraph(f"<font size=5.5 color='#D97706'><b>🛡️ {duty.duty_name}</b></font>", self.styles['GridCellSubject']))
                            else:
                                row.append(Paragraph("<font size=5.5 color='#10B981'><b>Available</b></font>", self.styles['GridCellDetail']))

                table_data.append(row)

            # Table row heights: header 22 pt, each teacher row ~10.5 pt
            r_heights = [22.0] + [10.5] * len(teachers)
            table = Table(table_data, colWidths=col_w, rowHeights=r_heights, repeatRows=1)
            table.setStyle(TableStyle(t_style))
            elements.append(table)

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
            leftMargin=30,
            rightMargin=30,
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

"""
Synchronized Practicals Alignment Wizard Dialog
Provides an intuitive UI to pair science and computer practicals across multiple sections
so the constraint solver schedules them simultaneously in parallel labs.
"""
import uuid
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox

from models.timetable_data import TimetableProject
from models.lesson import LessonAllocation

class SyncGroupWizardDialog(tb.Toplevel):
    def __init__(self, parent, project: TimetableProject, on_applied=None):
        super().__init__(parent)
        self.project = project
        self.on_applied = on_applied

        self.title("⚡ Aligned Science Practicals Wizard")
        self.geometry("720x580")
        self.resizable(False, False)

        self._build_ui()

    def _build_ui(self):
        # Header banner
        hdr = tb.Frame(self, bootstyle="info", padding=15)
        hdr.pack(fill=X)
        tb.Label(
            hdr,
            text="🔬 Multi-Section Aligned Science Practicals Setup",
            font=("Helvetica", 14, "bold"),
            bootstyle="inverse-info"
        ).pack(anchor=W)
        tb.Label(
            hdr,
            text="Simultaneously schedules practical labs across sections (e.g., Section A takes CS Lab while Section B takes Chemistry Lab, and then they swap).",
            font=("Helvetica", 8),
            bootstyle="inverse-info"
        ).pack(anchor=W, pady=(2, 0))

        content = tb.Frame(self, padding=20)
        content.pack(fill=BOTH, expand=True)

        # Section Selection
        sec_frame = tb.Labelframe(content, text=" Target Sections ", bootstyle="secondary", padding=10)
        sec_frame.pack(fill=X, pady=(0, 15))
        sec_frame.columnconfigure(0, weight=1)
        sec_frame.columnconfigure(1, weight=1)

        sec_choices = [f"{s.display_name} [{s.id}]" for s in self.project.sections.values()]

        f_s1 = tb.Frame(sec_frame)
        f_s1.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        tb.Label(f_s1, text="Section 1 (e.g. Sec A):").pack(anchor=W)
        self.combo_sec1 = tb.Combobox(f_s1, values=sec_choices, state="readonly")
        self.combo_sec1.pack(fill=X)
        if len(sec_choices) > 0:
            self.combo_sec1.set(sec_choices[0])

        f_s2 = tb.Frame(sec_frame)
        f_s2.grid(row=0, column=1, sticky="ew")
        tb.Label(f_s2, text="Section 2 (e.g. Sec B):").pack(anchor=W)
        self.combo_sec2 = tb.Combobox(f_s2, values=sec_choices, state="readonly")
        self.combo_sec2.pack(fill=X)
        if len(sec_choices) > 1:
            self.combo_sec2.set(sec_choices[1])

        # Practical Pair 1 Card (Simultaneous Slot 1)
        p1_card = tb.Labelframe(content, text=" Aligned Session 1 (Simultaneous Lab Block) ", bootstyle="primary", padding=10)
        p1_card.pack(fill=X, pady=(0, 10))
        p1_card.columnconfigure(0, weight=1)
        p1_card.columnconfigure(1, weight=1)

        sub_choices = [f"{s.name} ({s.code}) [{s.id}]" for s in self.project.subjects.values()]
        teach_choices = [f"{t.name} [{t.id}]" for t in self.project.teachers.values()]
        room_choices = [f"{r.name} [{r.id}]" for r in self.project.classrooms.values()]

        # Pair 1: Sec 1 Subject + Teacher + Lab
        f_p1_s1 = tb.Frame(p1_card)
        f_p1_s1.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        tb.Label(f_p1_s1, text="Section 1 Lab Subject:", font=("Helvetica", 8, "bold")).pack(anchor=W)
        self.combo_p1_sub1 = tb.Combobox(f_p1_s1, values=sub_choices, state="readonly")
        self.combo_p1_sub1.pack(fill=X, pady=2)
        tb.Label(f_p1_s1, text="Section 1 Teacher & Lab Room:").pack(anchor=W)
        self.combo_p1_t1 = tb.Combobox(f_p1_s1, values=teach_choices, state="readonly")
        self.combo_p1_t1.pack(fill=X, pady=2)
        self.combo_p1_r1 = tb.Combobox(f_p1_s1, values=room_choices, state="readonly")
        self.combo_p1_r1.pack(fill=X, pady=2)

        # Pair 1: Sec 2 Subject + Teacher + Lab
        f_p1_s2 = tb.Frame(p1_card)
        f_p1_s2.grid(row=0, column=1, sticky="ew")
        tb.Label(f_p1_s2, text="Section 2 Lab Subject:", font=("Helvetica", 8, "bold")).pack(anchor=W)
        self.combo_p1_sub2 = tb.Combobox(f_p1_s2, values=sub_choices, state="readonly")
        self.combo_p1_sub2.pack(fill=X, pady=2)
        tb.Label(f_p1_s2, text="Section 2 Teacher & Lab Room:").pack(anchor=W)
        self.combo_p1_t2 = tb.Combobox(f_p1_s2, values=teach_choices, state="readonly")
        self.combo_p1_t2.pack(fill=X, pady=2)
        self.combo_p1_r2 = tb.Combobox(f_p1_s2, values=room_choices, state="readonly")
        self.combo_p1_r2.pack(fill=X, pady=2)

        # Practical Pair 2 Card (The Swap Slot!)
        p2_card = tb.Labelframe(content, text=" Aligned Session 2 (The Lab Swap Block) ", bootstyle="success", padding=10)
        p2_card.pack(fill=X, pady=(0, 15))
        p2_card.columnconfigure(0, weight=1)
        p2_card.columnconfigure(1, weight=1)

        # In Pair 2, Sec 1 gets Sub 2, and Sec 2 gets Sub 1!
        f_p2_s1 = tb.Frame(p2_card)
        f_p2_s1.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        tb.Label(f_p2_s1, text="Section 1 takes Swap Lab:", font=("Helvetica", 8, "bold")).pack(anchor=W)
        self.combo_p2_sub1 = tb.Combobox(f_p2_s1, values=sub_choices, state="readonly")
        self.combo_p2_sub1.pack(fill=X, pady=2)
        tb.Label(f_p2_s1, text="Teacher & Lab:").pack(anchor=W)
        self.combo_p2_t1 = tb.Combobox(f_p2_s1, values=teach_choices, state="readonly")
        self.combo_p2_t1.pack(fill=X, pady=2)
        self.combo_p2_r1 = tb.Combobox(f_p2_s1, values=room_choices, state="readonly")
        self.combo_p2_r1.pack(fill=X, pady=2)

        f_p2_s2 = tb.Frame(p2_card)
        f_p2_s2.grid(row=0, column=1, sticky="ew")
        tb.Label(f_p2_s2, text="Section 2 takes Swap Lab:", font=("Helvetica", 8, "bold")).pack(anchor=W)
        self.combo_p2_sub2 = tb.Combobox(f_p2_s2, values=sub_choices, state="readonly")
        self.combo_p2_sub2.pack(fill=X, pady=2)
        tb.Label(f_p2_s2, text="Teacher & Lab:").pack(anchor=W)
        self.combo_p2_t2 = tb.Combobox(f_p2_s2, values=teach_choices, state="readonly")
        self.combo_p2_t2.pack(fill=X, pady=2)
        self.combo_p2_r2 = tb.Combobox(f_p2_s2, values=room_choices, state="readonly")
        self.combo_p2_r2.pack(fill=X, pady=2)

        # Bottom Buttons
        btn_row = tb.Frame(content)
        btn_row.pack(fill=X)

        tb.Button(btn_row, text="⚡ Apply Aligned Science Practicals", bootstyle="success", command=self._on_apply).pack(side=RIGHT, padx=5)
        tb.Button(btn_row, text="Cancel", bootstyle="secondary-outline", command=self.destroy).pack(side=RIGHT)

    def _parse_id(self, text: str) -> str:
        if "[" in text and text.endswith("]"):
            return text.split("[")[-1].rstrip("]")
        return ""

    def _on_apply(self):
        sec1_id = self._parse_id(self.combo_sec1.get())
        sec2_id = self._parse_id(self.combo_sec2.get())

        if not sec1_id or not sec2_id or sec1_id == sec2_id:
            messagebox.showerror("Error", "Please select two distinct sections to synchronize.")
            return

        # Session 1
        p1_sub1 = self._parse_id(self.combo_p1_sub1.get())
        p1_t1 = self._parse_id(self.combo_p1_t1.get())
        p1_r1 = self._parse_id(self.combo_p1_r1.get())

        p1_sub2 = self._parse_id(self.combo_p1_sub2.get())
        p1_t2 = self._parse_id(self.combo_p1_t2.get())
        p1_r2 = self._parse_id(self.combo_p1_r2.get())

        # Session 2
        p2_sub1 = self._parse_id(self.combo_p2_sub1.get())
        p2_t1 = self._parse_id(self.combo_p2_t1.get())
        p2_r1 = self._parse_id(self.combo_p2_r1.get())

        p2_sub2 = self._parse_id(self.combo_p2_sub2.get())
        p2_t2 = self._parse_id(self.combo_p2_t2.get())
        p2_r2 = self._parse_id(self.combo_p2_r2.get())

        if not (p1_sub1 and p1_t1 and p1_sub2 and p1_t2 and p2_sub1 and p2_t1 and p2_sub2 and p2_t2):
            messagebox.showerror("Error", "Please fill in all subject and teacher assignments for both sessions.")
            return

        # Unique sync group identifiers
        sync_id_1 = f"SYNC_PRAC_PAIR_{uuid.uuid4().hex[:6]}"
        sync_id_2 = f"SYNC_PRAC_PAIR_{uuid.uuid4().hex[:6]}"

        # Create Session 1 allocations (2-period double block)
        L1_A = LessonAllocation(
            id=f"L_{uuid.uuid4().hex[:6]}",
            section_id=sec1_id,
            subject_id=p1_sub1,
            teacher_id=p1_t1,
            room_id=p1_r1,
            periods_per_week=2,
            block_size=2,
            sync_group_id=sync_id_1,
            sync_group_name="Aligned Practicals Slot 1"
        )
        L1_B = LessonAllocation(
            id=f"L_{uuid.uuid4().hex[:6]}",
            section_id=sec2_id,
            subject_id=p1_sub2,
            teacher_id=p1_t2,
            room_id=p1_r2,
            periods_per_week=2,
            block_size=2,
            sync_group_id=sync_id_1,
            sync_group_name="Aligned Practicals Slot 1"
        )

        # Create Session 2 allocations (The Swap!)
        L2_A = LessonAllocation(
            id=f"L_{uuid.uuid4().hex[:6]}",
            section_id=sec1_id,
            subject_id=p2_sub1,
            teacher_id=p2_t1,
            room_id=p2_r1,
            periods_per_week=2,
            block_size=2,
            sync_group_id=sync_id_2,
            sync_group_name="Aligned Practicals Slot 2"
        )
        L2_B = LessonAllocation(
            id=f"L_{uuid.uuid4().hex[:6]}",
            section_id=sec2_id,
            subject_id=p2_sub2,
            teacher_id=p2_t2,
            room_id=p2_r2,
            periods_per_week=2,
            block_size=2,
            sync_group_id=sync_id_2,
            sync_group_name="Aligned Practicals Slot 2"
        )

        self.project.lessons[L1_A.id] = L1_A
        self.project.lessons[L1_B.id] = L1_B
        self.project.lessons[L2_A.id] = L2_A
        self.project.lessons[L2_B.id] = L2_B

        if self.on_applied:
            self.on_applied()

        messagebox.showinfo(
            "Aligned Practicals Created!",
            "Synchronized science practical pairs created successfully!\n\n"
            "The solver will schedule Session 1 simultaneously for both sections, "
            "and Session 2 as the simultaneous swap!"
        )
        self.destroy()

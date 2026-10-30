"""
Classes & Sections View
Manages academic grade levels and multi-section classes with student counts and base rooms.
"""
import uuid
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox

from models.timetable_data import TimetableProject
from models.section import GradeClass, Section

class ClassesView(tb.Frame):
    def __init__(self, parent, project: TimetableProject, on_update_callback=None):
        super().__init__(parent)
        self.project = project
        self.on_update_callback = on_update_callback
        self.selected_section_id = None

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Header
        header = tb.Frame(self)
        header.pack(fill=X, padx=20, pady=(15, 10))
        tb.Label(header, text="Classes & Multi-Section Directory", font=("Helvetica", 16, "bold"), bootstyle="primary").pack(side=LEFT)

        # Content split
        content = tb.Frame(self)
        content.pack(fill=BOTH, expand=True, padx=20, pady=10)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)

        # Left: Treeview
        tbl_frame = tb.Frame(content)
        tbl_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        cols = ("class", "section", "incharge", "students", "homeroom")
        self.tree = tb.Treeview(tbl_frame, columns=cols, show="headings", height=12, bootstyle="primary")
        self.tree.heading("class", text="Grade / Class Level")
        self.tree.heading("section", text="Section Name")
        self.tree.heading("incharge", text="Class Teacher / Incharge")
        self.tree.heading("students", text="Student Count")
        self.tree.heading("homeroom", text="Base Classroom")

        self.tree.column("class", width=130, anchor=W)
        self.tree.column("section", width=110, anchor=W)
        self.tree.column("incharge", width=160, anchor=W)
        self.tree.column("students", width=90, anchor=CENTER)
        self.tree.column("homeroom", width=130, anchor=W)

        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        sb = tb.Scrollbar(tbl_frame, orient="vertical", command=self.tree.yview)
        sb.pack(side=RIGHT, fill=Y)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Right: Manage Form
        form_card = tb.Labelframe(content, text=" Section Details & Editor ", bootstyle="secondary", padding=15)
        form_card.grid(row=0, column=1, sticky="nsew")

        tb.Label(form_card, text="Grade / Class Level:").pack(anchor=W, pady=(0, 2))
        self.combo_class = tb.Combobox(form_card, state="normal")
        self.combo_class.pack(fill=X, pady=(0, 8))

        tb.Label(form_card, text="Section Name (e.g. Section A, Section B):").pack(anchor=W, pady=(2, 2))
        self.entry_sec_name = tb.Entry(form_card)
        self.entry_sec_name.pack(fill=X, pady=(0, 8))

        tb.Label(form_card, text="Student Count / Strength:").pack(anchor=W, pady=(2, 2))
        self.spin_count = tb.Spinbox(form_card, from_=5, to=80, width=8)
        self.spin_count.pack(anchor=W, pady=(0, 8))

        tb.Label(form_card, text="Default Base Classroom:").pack(anchor=W, pady=(2, 2))
        self.combo_room = tb.Combobox(form_card, state="readonly")
        self.combo_room.pack(fill=X, pady=(0, 8))

        tb.Label(form_card, text="Designated Class Teacher / Incharge:", font=("Helvetica", 9, "bold"), bootstyle="primary").pack(anchor=W, pady=(2, 2))
        self.combo_teacher = tb.Combobox(form_card, state="readonly")
        self.combo_teacher.pack(fill=X, pady=(0, 15))

        # Buttons
        btn_box = tb.Frame(form_card)
        btn_box.pack(fill=X, pady=(10, 0))

        tb.Button(btn_box, text="➕ Add Section", bootstyle="success", command=self._on_add).pack(side=LEFT, padx=3)
        tb.Button(btn_box, text="💾 Update", bootstyle="primary", command=self._on_update).pack(side=LEFT, padx=3)
        tb.Button(btn_box, text="🗑️ Delete", bootstyle="danger", command=self._on_delete).pack(side=LEFT, padx=3)
        tb.Button(btn_box, text="Clear", bootstyle="secondary-outline", command=self._clear_form).pack(side=RIGHT, padx=3)

    def _parse_id(self, text: str) -> str:
        if "[" in text and text.endswith("]"):
            return text.split("[")[-1].rstrip("]")
        return ""

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for sec_id, sec in self.project.sections.items():
            room = self.project.classrooms.get(sec.home_room_id)
            r_name = room.name if room else "—"
            teacher = self.project.teachers.get(sec.class_teacher_id)
            t_name = f"{teacher.name} ({teacher.code})" if teacher else "— Not Assigned —"
            self.tree.insert("", "end", iid=sec_id, values=(sec.class_name, sec.name, t_name, sec.student_count, r_name))

        # Update comboboxes
        class_names = sorted(list({c.name for c in self.project.classes.values()}))
        self.combo_class['values'] = class_names

        room_names = ["(None)"] + [f"{r.name} ({r.room_type})" for r in self.project.classrooms.values()]
        self.combo_room['values'] = room_names

        teach_names = ["(None / Unassigned)"] + [f"{t.name} ({t.code}) [{t.id}]" for t in self.project.teachers.values()]
        self.combo_teacher['values'] = teach_names

        if self.selected_section_id and self.selected_section_id in self.project.sections:
            self.tree.selection_set(self.selected_section_id)

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        sec_id = sel[0]
        self.selected_section_id = sec_id
        sec = self.project.sections.get(sec_id)
        if sec:
            self.combo_class.set(sec.class_name)
            self.entry_sec_name.delete(0, "end")
            self.entry_sec_name.insert(0, sec.name)
            self.spin_count.set(sec.student_count)

            room = self.project.classrooms.get(sec.home_room_id)
            if room:
                self.combo_room.set(f"{room.name} ({room.room_type})")
            else:
                self.combo_room.set("(None)")

            teacher = self.project.teachers.get(sec.class_teacher_id)
            if teacher:
                self.combo_teacher.set(f"{teacher.name} ({teacher.code}) [{teacher.id}]")
            else:
                self.combo_teacher.set("(None / Unassigned)")

    def _clear_form(self):
        self.selected_section_id = None
        self.entry_sec_name.delete(0, "end")
        self.spin_count.set(30)
        self.combo_room.set("(None)")
        self.combo_teacher.set("(None / Unassigned)")
        self.tree.selection_remove(self.tree.selection())

    def _on_add(self):
        c_name = self.combo_class.get().strip()
        s_name = self.entry_sec_name.get().strip()
        if not c_name or not s_name:
            messagebox.showerror("Error", "Class Name and Section Name are required!")
            return

        # Ensure class exists
        c_obj = next((c for c in self.project.classes.values() if c.name == c_name), None)
        if not c_obj:
            c_id = f"c_{uuid.uuid4().hex[:6]}"
            c_obj = GradeClass(id=c_id, name=c_name)
            self.project.classes[c_id] = c_obj

        # Room ID
        r_str = self.combo_room.get()
        room_id = ""
        for r in self.project.classrooms.values():
            if f"{r.name} ({r.room_type})" == r_str:
                room_id = r.id
                break

        t_id = self._parse_id(self.combo_teacher.get())

        sec_id = f"s_{uuid.uuid4().hex[:6]}"
        sec = Section(
            id=sec_id,
            class_id=c_obj.id,
            class_name=c_obj.name,
            name=s_name,
            student_count=int(self.spin_count.get() or 30),
            home_room_id=room_id,
            class_teacher_id=t_id
        )
        self.project.sections[sec_id] = sec
        self.selected_section_id = sec_id
        self.refresh()
        if self.on_update_callback:
            self.on_update_callback()

    def _on_update(self):
        if not self.selected_section_id or self.selected_section_id not in self.project.sections:
            messagebox.showwarning("Warning", "Select a section to update.")
            return

        c_name = self.combo_class.get().strip()
        s_name = self.entry_sec_name.get().strip()
        if not c_name or not s_name:
            messagebox.showerror("Error", "Class Name and Section Name are required.")
            return

        sec = self.project.sections[self.selected_section_id]
        sec.class_name = c_name
        sec.name = s_name
        sec.student_count = int(self.spin_count.get() or 30)

        r_str = self.combo_room.get()
        room_id = ""
        for r in self.project.classrooms.values():
            if f"{r.name} ({r.room_type})" == r_str:
                room_id = r.id
                break
        sec.home_room_id = room_id

        t_id = self._parse_id(self.combo_teacher.get())
        sec.class_teacher_id = t_id

        self.refresh()
        if self.on_update_callback:
            self.on_update_callback()

    def _on_delete(self):
        if not self.selected_section_id:
            return
        sec = self.project.sections[self.selected_section_id]
        if messagebox.askyesno("Delete Section", f"Delete section '{sec.display_name}'?"):
            del self.project.sections[self.selected_section_id]
            self.selected_section_id = None
            self._clear_form()
            self.refresh()
            if self.on_update_callback:
                self.on_update_callback()

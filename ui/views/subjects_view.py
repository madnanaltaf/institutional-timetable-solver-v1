"""
Subjects & Curriculum View
Allows creating and editing subjects, assigning color codes, lab requirements,
and marking cognitively difficult subjects for fatigue avoidance.
"""
import uuid
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox, colorchooser

from models.timetable_data import TimetableProject
from models.subject import Subject, PALETTE_COLORS, ROOM_TYPES

SUBJECT_TYPES = ["Theory", "Practical Lab", "Elective", "Sports/PE", "Assembly"]

class SubjectsView(tb.Frame):
    def __init__(self, parent, project: TimetableProject, on_update_callback=None):
        super().__init__(parent)
        self.project = project
        self.on_update_callback = on_update_callback
        self.selected_subject_id = None
        self.current_color = PALETTE_COLORS[0]

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Header
        header = tb.Frame(self)
        header.pack(fill=X, padx=20, pady=(15, 10))
        tb.Label(header, text="Curriculum & Subjects Directory", font=("Helvetica", 16, "bold"), bootstyle="primary").pack(side=LEFT)

        # Content split
        content = tb.Frame(self)
        content.pack(fill=BOTH, expand=True, padx=20, pady=10)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)

        # Left: Table
        tbl_frame = tb.Frame(content)
        tbl_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        cols = ("code", "name", "type", "room_type", "difficult", "lab")
        self.tree = tb.Treeview(tbl_frame, columns=cols, show="headings", height=12, bootstyle="primary")
        self.tree.heading("code", text="Code")
        self.tree.heading("name", text="Subject Title")
        self.tree.heading("type", text="Type")
        self.tree.heading("room_type", text="Facility Required")
        self.tree.heading("difficult", text="Fatigue Avoidance")
        self.tree.heading("lab", text="Lab Required")

        self.tree.column("code", width=65, anchor=CENTER)
        self.tree.column("name", width=160, anchor=W)
        self.tree.column("type", width=95, anchor=W)
        self.tree.column("room_type", width=140, anchor=W)
        self.tree.column("difficult", width=110, anchor=CENTER)
        self.tree.column("lab", width=85, anchor=CENTER)

        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        sb = tb.Scrollbar(tbl_frame, orient="vertical", command=self.tree.yview)
        sb.pack(side=RIGHT, fill=Y)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Right: Form Card
        form_card = tb.Labelframe(content, text=" Subject Properties & Visual Styling ", bootstyle="secondary", padding=15)
        form_card.grid(row=0, column=1, sticky="nsew")

        r1 = tb.Frame(form_card)
        r1.pack(fill=X, pady=2)
        r1.columnconfigure(0, weight=1)
        r1.columnconfigure(1, weight=2)

        tb.Label(r1, text="Subject Code:").grid(row=0, column=0, sticky=W)
        self.entry_code = tb.Entry(r1, width=10)
        self.entry_code.grid(row=0, column=0, sticky=E, padx=(80, 10))

        tb.Label(r1, text="Subject Name:").grid(row=0, column=1, sticky=W)
        self.entry_name = tb.Entry(r1)
        self.entry_name.grid(row=0, column=1, sticky="ew", padx=(85, 0))

        tb.Label(form_card, text="Subject Type:").pack(anchor=W, pady=(6, 2))
        self.combo_type = tb.Combobox(form_card, values=SUBJECT_TYPES, state="readonly")
        self.combo_type.pack(fill=X, pady=(0, 6))

        tb.Label(form_card, text="Default Facility / Room Type:").pack(anchor=W, pady=(2, 2))
        self.combo_room_type = tb.Combobox(form_card, values=ROOM_TYPES, state="readonly")
        self.combo_room_type.pack(fill=X, pady=(0, 8))

        # Checkboxes for constraints
        self.var_lab = tb.BooleanVar()
        tb.Checkbutton(form_card, text="Requires Specialized Laboratory", variable=self.var_lab, bootstyle="round-toggle").pack(anchor=W, pady=2)

        self.var_diff = tb.BooleanVar()
        tb.Checkbutton(form_card, text="High Cognitive Difficulty (Avoid fatigue & late periods)", variable=self.var_diff, bootstyle="round-toggle").pack(anchor=W, pady=2)

        self.var_double = tb.BooleanVar()
        tb.Checkbutton(form_card, text="Allows 2-Period Consecutive Blocks (Lab Practical)", variable=self.var_double, bootstyle="round-toggle").pack(anchor=W, pady=2)

        # Color Selector
        tb.Label(form_card, text="Timetable Color Accent:").pack(anchor=W, pady=(8, 2))
        color_row = tb.Frame(form_card)
        color_row.pack(fill=X, pady=(0, 10))

        self.btn_color_preview = tb.Button(color_row, text="  Sample  ", bootstyle="primary", width=8, command=self._choose_custom_color)
        self.btn_color_preview.pack(side=LEFT, padx=(0, 8))

        palette_frame = tb.Frame(color_row)
        palette_frame.pack(side=LEFT, fill=X, expand=True)
        for c in PALETTE_COLORS[:6]:
            b = tb.Button(
                palette_frame, text=" ", width=2,
                command=lambda col=c: self._set_color(col)
            )
            b.configure(style="Secondary.TButton")
            b.pack(side=LEFT, padx=1)

        # Buttons
        btn_box = tb.Frame(form_card)
        btn_box.pack(fill=X, pady=(10, 0))

        tb.Button(btn_box, text="➕ Add Subject", bootstyle="success", command=self._on_add).pack(side=LEFT, padx=3)
        tb.Button(btn_box, text="💾 Update", bootstyle="primary", command=self._on_update).pack(side=LEFT, padx=3)
        tb.Button(btn_box, text="🗑️ Delete", bootstyle="danger", command=self._on_delete).pack(side=LEFT, padx=3)
        tb.Button(btn_box, text="Clear", bootstyle="secondary-outline", command=self._clear_form).pack(side=RIGHT, padx=3)

    def _set_color(self, hex_code: str):
        self.current_color = hex_code
        self.btn_color_preview.config(text=hex_code)

    def _choose_custom_color(self):
        color = colorchooser.askcolor(self.current_color, title="Choose Subject Color")
        if color and color[1]:
            self._set_color(color[1])

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for s_id, s in self.project.subjects.items():
            diff_lbl = "✓ High" if s.is_difficult else "Normal"
            lab_lbl = "✓ Lab" if s.requires_lab else "No"
            self.tree.insert("", "end", iid=s_id, values=(s.code, s.name, s.subject_type, s.default_room_type, diff_lbl, lab_lbl))

        if self.selected_subject_id and self.selected_subject_id in self.project.subjects:
            self.tree.selection_set(self.selected_subject_id)

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        s_id = sel[0]
        self.selected_subject_id = s_id
        sub = self.project.subjects.get(s_id)
        if sub:
            self.entry_code.delete(0, "end")
            self.entry_code.insert(0, sub.code)
            self.entry_name.delete(0, "end")
            self.entry_name.insert(0, sub.name)
            self.combo_type.set(sub.subject_type)
            self.combo_room_type.set(sub.default_room_type)
            self.var_lab.set(sub.requires_lab)
            self.var_diff.set(sub.is_difficult)
            self.var_double.set(sub.allowed_double_period)
            self._set_color(sub.color)

    def _clear_form(self):
        self.selected_subject_id = None
        self.entry_code.delete(0, "end")
        self.entry_name.delete(0, "end")
        self.combo_type.set(SUBJECT_TYPES[0])
        self.combo_room_type.set(ROOM_TYPES[0])
        self.var_lab.set(False)
        self.var_diff.set(False)
        self.var_double.set(False)
        self._set_color(PALETTE_COLORS[0])
        self.tree.selection_remove(self.tree.selection())

    def _on_add(self):
        code = self.entry_code.get().strip()
        name = self.entry_name.get().strip()
        if not code or not name:
            messagebox.showerror("Error", "Subject Code and Name are required!")
            return

        s_id = f"sub_{uuid.uuid4().hex[:6]}"
        sub = Subject(
            id=s_id,
            code=code,
            name=name,
            subject_type=self.combo_type.get().strip() or "Theory",
            color=self.current_color,
            requires_lab=self.var_lab.get(),
            default_room_type=self.combo_room_type.get().strip() or "General Classroom",
            is_difficult=self.var_diff.get(),
            allowed_double_period=self.var_double.get()
        )
        self.project.subjects[s_id] = sub
        self.selected_subject_id = s_id
        self.refresh()
        if self.on_update_callback:
            self.on_update_callback()

    def _on_update(self):
        if not self.selected_subject_id or self.selected_subject_id not in self.project.subjects:
            messagebox.showwarning("Warning", "Select a subject to update.")
            return

        code = self.entry_code.get().strip()
        name = self.entry_name.get().strip()
        if not code or not name:
            messagebox.showerror("Error", "Subject Code and Name cannot be empty.")
            return

        sub = self.project.subjects[self.selected_subject_id]
        sub.code = code
        sub.name = name
        sub.subject_type = self.combo_type.get().strip() or "Theory"
        sub.color = self.current_color
        sub.requires_lab = self.var_lab.get()
        sub.default_room_type = self.combo_room_type.get().strip() or "General Classroom"
        sub.is_difficult = self.var_diff.get()
        sub.allowed_double_period = self.var_double.get()

        self.refresh()
        if self.on_update_callback:
            self.on_update_callback()

    def _on_delete(self):
        if not self.selected_subject_id:
            return
        sub = self.project.subjects[self.selected_subject_id]
        if messagebox.askyesno("Delete Subject", f"Delete subject '{sub.name}'?"):
            del self.project.subjects[self.selected_subject_id]
            self.selected_subject_id = None
            self._clear_form()
            self.refresh()
            if self.on_update_callback:
                self.on_update_callback()

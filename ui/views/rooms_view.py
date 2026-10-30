"""
Rooms & Laboratories View
Manages standard lecture halls and specialized science/computer laboratories.
"""
import uuid
import ttkbootstrap as tb
from ttkbootstrap.constants import *
from tkinter import messagebox

from models.timetable_data import TimetableProject
from models.classroom import Classroom
from models.subject import ROOM_TYPES

class RoomsView(tb.Frame):
    def __init__(self, parent, project: TimetableProject, on_update_callback=None):
        super().__init__(parent)
        self.project = project
        self.on_update_callback = on_update_callback
        self.selected_room_id = None

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        # Header
        header = tb.Frame(self)
        header.pack(fill=X, padx=20, pady=(15, 10))
        tb.Label(header, text="Rooms & Specialized Science Laboratories", font=("Helvetica", 16, "bold"), bootstyle="primary").pack(side=LEFT)

        # Content split
        content = tb.Frame(self)
        content.pack(fill=BOTH, expand=True, padx=20, pady=10)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)

        # Left: Table
        tbl_frame = tb.Frame(content)
        tbl_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        cols = ("name", "type", "capacity", "building")
        self.tree = tb.Treeview(tbl_frame, columns=cols, show="headings", height=12, bootstyle="primary")
        self.tree.heading("name", text="Room / Lab Name")
        self.tree.heading("type", text="Facility Type")
        self.tree.heading("capacity", text="Student Capacity")
        self.tree.heading("building", text="Building / Wing")

        self.tree.column("name", width=160, anchor=W)
        self.tree.column("type", width=160, anchor=W)
        self.tree.column("capacity", width=100, anchor=CENTER)
        self.tree.column("building", width=140, anchor=W)

        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        sb = tb.Scrollbar(tbl_frame, orient="vertical", command=self.tree.yview)
        sb.pack(side=RIGHT, fill=Y)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Right: Form Card
        form_card = tb.Labelframe(content, text=" Room / Laboratory Configuration ", bootstyle="secondary", padding=15)
        form_card.grid(row=0, column=1, sticky="nsew")

        tb.Label(form_card, text="Room / Laboratory Name:").pack(anchor=W, pady=(0, 2))
        self.entry_name = tb.Entry(form_card)
        self.entry_name.pack(fill=X, pady=(0, 8))

        tb.Label(form_card, text="Facility Type:").pack(anchor=W, pady=(2, 2))
        self.combo_type = tb.Combobox(form_card, values=ROOM_TYPES, state="readonly")
        self.combo_type.pack(fill=X, pady=(0, 8))

        tb.Label(form_card, text="Student Capacity:").pack(anchor=W, pady=(2, 2))
        self.spin_capacity = tb.Spinbox(form_card, from_=10, to=200, width=8)
        self.spin_capacity.pack(anchor=W, pady=(0, 8))

        tb.Label(form_card, text="Building / Wing:").pack(anchor=W, pady=(2, 2))
        self.entry_building = tb.Entry(form_card)
        self.entry_building.pack(fill=X, pady=(0, 15))

        # Buttons
        btn_box = tb.Frame(form_card)
        btn_box.pack(fill=X, pady=(10, 0))

        tb.Button(btn_box, text="➕ Add Room", bootstyle="success", command=self._on_add).pack(side=LEFT, padx=3)
        tb.Button(btn_box, text="💾 Update", bootstyle="primary", command=self._on_update).pack(side=LEFT, padx=3)
        tb.Button(btn_box, text="🗑️ Delete", bootstyle="danger", command=self._on_delete).pack(side=LEFT, padx=3)
        tb.Button(btn_box, text="Clear", bootstyle="secondary-outline", command=self._clear_form).pack(side=RIGHT, padx=3)

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for r_id, r in self.project.classrooms.items():
            self.tree.insert("", "end", iid=r_id, values=(r.name, r.room_type, r.capacity, r.building))

        if self.selected_room_id and self.selected_room_id in self.project.classrooms:
            self.tree.selection_set(self.selected_room_id)

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        r_id = sel[0]
        self.selected_room_id = r_id
        room = self.project.classrooms.get(r_id)
        if room:
            self.entry_name.delete(0, "end")
            self.entry_name.insert(0, room.name)
            self.combo_type.set(room.room_type)
            self.spin_capacity.set(room.capacity)
            self.entry_building.delete(0, "end")
            self.entry_building.insert(0, room.building)

    def _clear_form(self):
        self.selected_room_id = None
        self.entry_name.delete(0, "end")
        self.combo_type.set(ROOM_TYPES[0])
        self.spin_capacity.set(40)
        self.entry_building.delete(0, "end")
        self.tree.selection_remove(self.tree.selection())

    def _on_add(self):
        name = self.entry_name.get().strip()
        r_type = self.combo_type.get().strip() or "General Classroom"
        if not name:
            messagebox.showerror("Error", "Room Name is required!")
            return

        r_id = f"r_{uuid.uuid4().hex[:6]}"
        room = Classroom(
            id=r_id,
            name=name,
            room_type=r_type,
            capacity=int(self.spin_capacity.get() or 40),
            building=self.entry_building.get().strip() or "Main Wing"
        )
        self.project.classrooms[r_id] = room
        self.selected_room_id = r_id
        self.refresh()
        if self.on_update_callback:
            self.on_update_callback()

    def _on_update(self):
        if not self.selected_room_id or self.selected_room_id not in self.project.classrooms:
            messagebox.showwarning("Warning", "Select a room to update.")
            return

        name = self.entry_name.get().strip()
        if not name:
            messagebox.showerror("Error", "Room Name cannot be empty.")
            return

        room = self.project.classrooms[self.selected_room_id]
        room.name = name
        room.room_type = self.combo_type.get().strip() or "General Classroom"
        room.capacity = int(self.spin_capacity.get() or 40)
        room.building = self.entry_building.get().strip()

        self.refresh()
        if self.on_update_callback:
            self.on_update_callback()

    def _on_delete(self):
        if not self.selected_room_id:
            return
        room = self.project.classrooms[self.selected_room_id]
        if messagebox.askyesno("Delete Room", f"Delete '{room.name}'?"):
            del self.project.classrooms[self.selected_room_id]
            self.selected_room_id = None
            self._clear_form()
            self.refresh()
            if self.on_update_callback:
                self.on_update_callback()

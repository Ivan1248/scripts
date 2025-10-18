#!/usr/bin/env python3
"""
DL-lab1 Scheduler GUI v2
- Deterministic color assignment (by order of appearance)
- Automatic parsing on data edit
- Uses Matplotlib tab10 color palette
- Supports multi-event overlap, full-day calendar display

Made using ChatGPT-5 and GitHub Copilot "Auto".
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timedelta
import re, os, zipfile
from collections import OrderedDict
from matplotlib import cm, colors

# ----------------------------------------
# Constants
# ----------------------------------------

# Window settings
WINDOW_SIZE = "1200x720"
PANE_SPLIT_RATIO = 0.4

# Visual settings
CALENDAR_BG_COLOR = "white"
HEADER_BG_COLOR = "#f0f0f0"
HEADER_BORDER_COLOR = "#ccc"
GRID_LINE_COLOR = "#eee"
TEXT_COLOR = {
    "normal": "#000000",
    "room": "#000000",
    "error": "red",
    "hint": "gray"
}

# Layout settings
LEFT_MARGIN = 60
TOP_MARGIN = 30
TEXT_AREA_HEIGHT = 18
TREEVIEW_HEIGHT = 8
TITLE_FONT = ("TkDefaultFont", 9)
ROOM_FONT = ("TkDefaultFont", 8, "bold")
NAME_FONT = ("TkDefaultFont", 8)
DATE_FONT = ("TkDefaultFont", 10, "bold")
HOUR_FONT = ("TkDefaultFont", 9)

# Timing settings
PARSE_DELAY_MS = 1000

# ----------------------------------------
# Parsing utilities
# ----------------------------------------

EVENT_RE = re.compile(
    r"(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<start>\d{1,2}:\d{2})\s+"
    r"(?P<end>\d{1,2}:\d{2})\s+"
    r"(?P<room>[A-Za-z0-9\-_]+)",
    flags=re.UNICODE,
)

def parse_schedule_block(text):
    matches = list(EVENT_RE.finditer(text))
    events = []
    for i, m in enumerate(matches):
        start_span = m.end()
        end_span = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        names_block = text[start_span:end_span].strip().replace("\r", " ").replace("\n", " ")
        parts = [p.strip() for p in re.split(r",|\t{1,}| {2,}", names_block) if p.strip()]
        events.append({
            "date": m.group("date"),
            "start": m.group("start"),
            "end": m.group("end"),
            "room": m.group("room"),
            "names": parts
        })
    return events

# ----------------------------------------
# iCalendar generation
# ----------------------------------------

def dt_to_ical(dt): return dt.strftime("%Y%m%dT%H%M%S")

def create_ics_for_person(person_name, events, title, out_folder):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//DL-lab1 Scheduler//EN"]
    for idx, ev in enumerate(events):
        start_dt = datetime.strptime(f"{ev['date']} {ev['start']}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{ev['date']} {ev['end']}", "%Y-%m-%d %H:%M")
        uid = f"{person_name.replace(' ', '_')}_{idx}@dl-lab1"
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{dt_to_ical(datetime.utcnow())}Z",
            f"DTSTART:{dt_to_ical(start_dt)}",
            f"DTEND:{dt_to_ical(end_dt)}",
            f"SUMMARY:{title}",
            f"LOCATION:{ev['room']}",
            f"DESCRIPTION:Participants: {', '.join(ev.get('names', []))}",
            "END:VEVENT"
        ]
    lines.append("END:VCALENDAR")
    out_path = os.path.join(out_folder, f"{person_name.replace(' ', '_')}.ics")
    with open(out_path, "w", encoding="utf-8") as f: f.write("\n".join(lines))
    return out_path

# ----------------------------------------
# Color utilities (deterministic, order-based)
# ----------------------------------------

PALETTE = [colors.to_hex(c) for c in cm.Pastel1.colors]

class ColorManager:
    def __init__(self):
        self.room_colors = OrderedDict()

    def color_for_room(self, room):
        if room not in self.room_colors:
            idx = len(self.room_colors) % len(PALETTE)
            self.room_colors[room] = PALETTE[idx]
        return self.room_colors[room]

# ----------------------------------------
# GUI
# ----------------------------------------

class SchedulerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DL-lab1 Scheduler")
        self.geometry(WINDOW_SIZE)

        self.colors = ColorManager()
        self.parse_after_id = None

        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(paned, padding=6)
        right = ttk.Frame(paned, padding=6)
        paned.add(left, weight=1)
        paned.add(right, weight=2)
        self.after(100, lambda: paned.sashpos(0, int(self.winfo_width() * PANE_SPLIT_RATIO)))

        # ---- Controls ----
        top = ttk.Frame(left)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Title:").pack(side=tk.LEFT)
        self.title_var = tk.StringVar(value="DL-lab1")
        ttk.Entry(top, textvariable=self.title_var, width=30).pack(side=tk.LEFT, padx=6)
        ttk.Button(top, text="Export selected (.ics)", command=self.on_export_one).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text="Export all (.zip)", command=self.on_export_zip).pack(side=tk.LEFT, padx=4)

        ttk.Label(left, text="Data (paste schedule):").pack(anchor="w", pady=(8, 0))
        text_frame = ttk.Frame(left)
        text_frame.pack(fill=tk.BOTH, expand=True)
        self.text = tk.Text(text_frame, wrap="none", height=TEXT_AREA_HEIGHT)
        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        ysb = ttk.Scrollbar(text_frame, command=self.text.yview)
        ysb.pack(side=tk.RIGHT, fill=tk.Y)
        self.text.configure(yscrollcommand=ysb.set)
        self.text.bind("<<Modified>>", self.on_text_modified)

        ttk.Label(left, text="Filter by person:").pack(anchor="w", pady=(8, 0))
        self.person_var = tk.StringVar(value="(All)")
        self.person_combo = ttk.Combobox(left, textvariable=self.person_var, state="readonly")
        self.person_combo.pack(fill=tk.X)
        self.person_combo.bind("<<ComboboxSelected>>", lambda e: self.draw_calendar())

        ttk.Label(left, text="Parsed events:").pack(anchor="w", pady=(8, 0))
        self.tree = ttk.Treeview(left, columns=("date", "start", "end", "room", "names"), show="headings", height=TREEVIEW_HEIGHT)
        for c in ("date", "start", "end", "room", "names"):
            self.tree.heading(c, text=c)
            self.tree.column(c, width=100, anchor="w")
        self.tree.pack(fill=tk.BOTH, expand=True)

        # ---- Calendar ----
        ttk.Label(right, text="Calendar view:").pack(anchor="w")
        self.canvas = tk.Canvas(right, bg=CALENDAR_BG_COLOR)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda e: self.draw_calendar())

        self.events, self.by_person = [], {}

    # ---------------- Automatic parsing ----------------

    def on_text_modified(self, event=None):
        if self.text.edit_modified():
            if self.parse_after_id:
                self.after_cancel(self.parse_after_id)
            self.parse_after_id = self.after(PARSE_DELAY_MS, self.on_parse)
            self.text.edit_modified(False)

    # ---------------- Parse and export ----------------

    def on_parse(self):
        try:
            raw = self.text.get("1.0", "end").strip()
            if not raw:
                self.events = []
                self.by_person = {}
                self.draw_calendar()
                return
                
            self.events = parse_schedule_block(raw)
            if not self.events:
                self.canvas.delete("all")
                self.canvas.create_text(20, 20, anchor="nw", 
                    text="No events found. Make sure the format is:\nYYYY-MM-DD HH:MM HH:MM ROOM\nName1, Name2, ...", 
                    fill=TEXT_COLOR["hint"])
                self.by_person = {}
                return
        except Exception as e:
            self.canvas.delete("all")
            self.canvas.create_text(20, 20, anchor="nw", 
                text=f"Error parsing schedule:\n{str(e)}\n\nExpected format:\nYYYY-MM-DD HH:MM HH:MM ROOM\nName1, Name2, ...", 
                fill=TEXT_COLOR["error"])
            self.events = []
            self.by_person = {}
            return

        self.colors = ColorManager()  # Reset colors by order of appearance
        self.by_person = {}
        for ev in self.events:
            self.colors.color_for_room(ev["room"])  # Pre-assign colors to rooms
            for n in ev.get("names", []):
                self.by_person.setdefault(n, []).append(ev)

        people = sorted(self.by_person.keys())
        self.person_combo["values"] = ["(All)"] + people
        if self.person_var.get() not in people:
            self.person_combo.set("(All)")

        for i in self.tree.get_children():
            self.tree.delete(i)
        for ev in self.events:
            self.tree.insert("", "end", values=(ev["date"], ev["start"], ev["end"], ev["room"], ", ".join(ev["names"])))

        self.draw_calendar()

    def on_export_one(self):
        if not self.by_person:
            messagebox.showwarning("No data", "Parse data first.")
            return
        person = self.person_var.get()
        if person == "(All)":
            messagebox.showinfo("Select person", "Please select a person to export.")
            return
        folder = filedialog.askdirectory(title="Select output folder")
        if not folder:
            return
        create_ics_for_person(person, self.by_person[person], self.title_var.get(), folder)
        messagebox.showinfo("Done", f"Exported calendar for {person} to {folder}")

    def on_export_zip(self):
        if not self.by_person:
            messagebox.showwarning("No data", "Parse data first.")
            return
        zip_path = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("ZIP files", "*.zip")])
        if not zip_path:
            return
        tmp = os.path.join(os.getcwd(), "_ics_tmp")
        os.makedirs(tmp, exist_ok=True)
        paths = [create_ics_for_person(p, evs, self.title_var.get(), tmp) for p, evs in self.by_person.items()]
        with zipfile.ZipFile(zip_path, "w") as zf:
            for p in paths:
                zf.write(p, arcname=os.path.basename(p))
        for p in paths: os.remove(p)
        os.rmdir(tmp)
        messagebox.showinfo("Done", f"Exported {len(paths)} calendars into {zip_path}")

    # ---------------- Calendar rendering ----------------

    def draw_calendar(self):
        cv = self.canvas
        cv.delete("all")
        if not self.events:
            cv.create_text(20, 20, anchor="nw", text="No events parsed.", fill=TEXT_COLOR["hint"])
            return

        person = self.person_var.get()
        evs = self.events if person == "(All)" else self.by_person.get(person, [])
        if not evs:
            cv.create_text(20, 20, anchor="nw", text="No events for this person.", fill=TEXT_COLOR["hint"])
            return

        dates = sorted({datetime.strptime(e["date"], "%Y-%m-%d") for e in evs})
        first_day, last_day = min(dates), max(dates)
        all_days = [(first_day + timedelta(days=i)) for i in range((last_day - first_day).days + 1)]

        min_h, max_h, parsed = 24, 0, []
        for ev in evs:
            s = datetime.strptime(f"{ev['date']} {ev['start']}", "%Y-%m-%d %H:%M")
            e = datetime.strptime(f"{ev['date']} {ev['end']}", "%Y-%m-%d %H:%M")
            parsed.append((s, e, ev))
            min_h, max_h = min(min_h, s.hour), max(max_h, e.hour)
        min_h, max_h = max(0, min_h - 1), min(23, max_h + 1)

        w, h = cv.winfo_width(), cv.winfo_height()
        col_w = (w - LEFT_MARGIN) / len(all_days)
        hours = list(range(min_h, max_h + 1))
        row_h = (h - TOP_MARGIN) / len(hours)

        for i, d in enumerate(all_days):
            x0 = LEFT_MARGIN + i * col_w
            cv.create_rectangle(x0, 0, x0 + col_w, TOP_MARGIN, fill=HEADER_BG_COLOR, outline=HEADER_BORDER_COLOR)
            cv.create_text(x0 + 4, TOP_MARGIN / 2, anchor="w", text=d.strftime("%a %Y-%m-%d"), font=DATE_FONT)
        for j, hr in enumerate(hours):
            y = TOP_MARGIN + j * row_h
            cv.create_text(LEFT_MARGIN - 5, y + row_h / 2, anchor="e", text=f"{hr:02d}:00", font=HOUR_FONT)
            for i in range(len(all_days)):
                x0 = LEFT_MARGIN + i * col_w
                cv.create_rectangle(x0, y, x0 + col_w, y + row_h, outline=GRID_LINE_COLOR)

        events_by_day = {d.strftime("%Y-%m-%d"): [] for d in all_days}
        for s, e, ev in parsed:
            events_by_day[ev["date"]].append((s, e, ev))

        for day_index, d in enumerate(all_days):
            slot_groups = []
            for s, e, ev in sorted(events_by_day.get(d.strftime("%Y-%m-%d"), []), key=lambda x: x[0]):
                for slot in slot_groups:
                    if all(e <= se or s >= ee for se, ee, _ in slot):
                        slot.append((s, e, ev))
                        break
                else:
                    slot_groups.append([(s, e, ev)])
            for slot_idx, slot in enumerate(slot_groups):
                subw = col_w / len(slot_groups)
                for s, e, ev in slot:
                    y0 = TOP_MARGIN + (s.hour - min_h + s.minute / 60) * row_h
                    y1 = TOP_MARGIN + (e.hour - min_h + e.minute / 60) * row_h
                    x0 = LEFT_MARGIN + day_index * col_w + slot_idx * subw
                    x1 = x0 + subw - 2  # 2px right padding
                    bg = self.colors.color_for_room(ev["room"])
                    cv.create_rectangle(x0, y0, x1, y1 - 2, fill=bg, outline=CALENDAR_BG_COLOR)  # 2px bottom padding
                    y = y0 + 2
                    
                    # Start text placement with padding from top
                    event_height = y1 - y0
                    y = y0 + 2
                    
                    # Show title and room at the top
                    title_text = cv.create_text(x0 + 3, y, anchor="nw", text=self.title_var.get(), 
                                            fill=TEXT_COLOR["room"], font=TITLE_FONT)
                    title_bbox = cv.bbox(title_text)
                    y += title_bbox[3] - title_bbox[1] + 1  # Height of title text + small gap
                    
                    room_text = cv.create_text(x0 + 3, y, anchor="nw", text=f"[{ev['room']}]", 
                                            fill=TEXT_COLOR["room"], font=ROOM_FONT)
                    room_bbox = cv.bbox(room_text)
                    y += room_bbox[3] - room_bbox[1] + 2  # Height of room text + small gap
                    
                    # Show names below room, with wrapping
                    for nm in ev["names"]:
                        if y + 12 > y1 - 2:  # Stop if we're out of space (2px bottom padding)
                            break
                        name_text = cv.create_text(x0 + 3, y, anchor="nw", text=nm, 
                                                fill=TEXT_COLOR["normal"], font=NAME_FONT,
                                                width=subw - 6)  # Enable text wrapping
                        name_bbox = cv.bbox(name_text)
                        y += name_bbox[3] - name_bbox[1] + 2  # Actual height of wrapped text + small gap

# ----------------------------------------
if __name__ == "__main__":
    SchedulerApp().mainloop()

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
import os
import re
import zipfile
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
    """Parse the schedule text and return (events, errors).

    events: list of parsed event dicts
    errors: list of (line_no, message) tuples describing parse problems
    """
    matches = list(EVENT_RE.finditer(text))
    events = []
    errors = []
    if not matches:
        # Try to detect common problems: empty or bad-format lines
        lines = [line for line in text.splitlines() if line.strip()]
        if lines:
            for ln, line in enumerate(lines, start=1):
                if not EVENT_RE.match(line):
                    errors.append((ln, "Unrecognized line format: " + line))
        return events, errors

    # We'll map character offsets to line numbers for better error messages
    line_starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            line_starts.append(i + 1)

    def charpos_to_lineno(pos):
        # Binary search would be overkill; linear scan is fine for small inputs
        ln = 1
        for start in line_starts:
            if pos >= start:
                ln += 1
            else:
                break
        return max(1, ln - 1)

    for i, m in enumerate(matches):
        try:
            start_span = m.end()
            end_span = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            names_block = text[start_span:end_span].strip().replace("\r", " ").replace("\n", " ")
            parts = [p.strip() for p in re.split(r",|\t{1,}| {2,}", names_block) if p.strip()]
            ev = {
                "date": m.group("date"),
                "start": m.group("start"),
                "end": m.group("end"),
                "room": m.group("room"),
                "names": parts,
                "_match_span": (m.start(), m.end())
            }
            # Validate datetime fields quickly
            try:
                datetime.strptime(f"{ev['date']} {ev['start']}", "%Y-%m-%d %H:%M")
                datetime.strptime(f"{ev['date']} {ev['end']}", "%Y-%m-%d %H:%M")
            except Exception as dt_e:
                lineno = charpos_to_lineno(m.start())
                errors.append((lineno, f"Invalid date/time: {dt_e}"))
            events.append(ev)
        except Exception as e:
            lineno = charpos_to_lineno(m.start())
            errors.append((lineno, f"Failed to parse event at pos {m.start()}: {e}"))

    # Detect standalone date tokens that don't correspond to a full EVENT_RE match
    # (these indicate incomplete/malformed event lines such as missing start/end/room)
    match_starts = {m.start() for m in matches}
    for dm in re.finditer(r"\d{4}-\d{2}-\d{2}", text):
        if dm.start() not in match_starts:
            lineno = charpos_to_lineno(dm.start())
            # Extract the full physical line for context
            line_start = text.rfind("\n", 0, dm.start())
            line_end = text.find("\n", dm.start())
            if line_start == -1:
                line_start = 0
            else:
                line_start += 1
            if line_end == -1:
                line_end = len(text)
            excerpt = text[line_start:line_end].strip()
            errors.append((lineno, "Incomplete or malformed event: " + excerpt))

    return events, errors

# ----------------------------------------
# iCalendar generation
# ----------------------------------------

def dt_to_ical(dt): return dt.strftime("%Y%m%dT%H%M%S")

def create_ics_for_person(person_name, events, title, out_path=None):
    """Create an .ics file for a person.

    If out_path is provided, the file will be written directly to that path.
    Otherwise it's written to the current working directory as
    <Person>.ics. Returns the full path to the written file.
    """
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

    # Decide where to write the file
    out_path_final = out_path if out_path else os.path.join(os.getcwd(), f"{person_name.replace(' ', '_')}.ics")

    # Ensure containing directory exists for an explicit out_path
    parent = os.path.dirname(out_path_final)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)

    with open(out_path_final, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return out_path_final

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

        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left)
        paned.add(right)
        paned.pane(left, weight=3)
        paned.pane(right, weight=2)

        min_left_width = 460
        min_right_width = 200

        def sash_limits(total_width):
            max_left = max(0, total_width - min_right_width)
            min_left = min(min_left_width, max_left)
            return min_left, max_left

        def enforce_sash_limits():
            total = paned.winfo_width()
            if total <= 1:
                return
            min_pos, max_pos = sash_limits(total)
            try:
                current = paned.sashpos(0)
            except tk.TclError:
                current = min_pos
            if current < min_pos:
                paned.sashpos(0, min_pos)
            elif current > max_pos:
                paned.sashpos(0, max_pos)

        def set_initial_sash():
            total = paned.winfo_width()
            if total <= 1:
                self.after(20, set_initial_sash)
                return
            min_pos, max_pos = sash_limits(total)
            desired = int(total * PANE_SPLIT_RATIO)
            paned.sashpos(0, min(max(desired, min_pos), max_pos))
            enforce_sash_limits()

        self.after(20, set_initial_sash)
        paned.bind("<Configure>", lambda e: enforce_sash_limits())

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

        ttk.Label(left, text="Parsing messages:").pack(anchor="w", pady=(8, 0))
        msg_frame = ttk.Frame(left)
        msg_frame.pack(fill=tk.BOTH, expand=False)
        self.error_text = tk.Text(msg_frame, height=6, wrap="word", foreground=TEXT_COLOR["error"] )
        self.error_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        msg_ysb = ttk.Scrollbar(msg_frame, command=self.error_text.yview)
        msg_ysb.pack(side=tk.LEFT, fill=tk.Y)
        self.error_text.configure(yscrollcommand=msg_ysb.set)
        btn_frame = ttk.Frame(msg_frame)
        btn_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(6,0))
        ttk.Button(btn_frame, text="Copy", command=lambda: self._copy_error_text(None)).pack(anchor="n")
        # Bind copy/select shortcuts so users can copy messages even when widget is read-only
        # We'll set the widget to DISABLED after populating it; these bindings still work.
        self.error_text.bind("<Control-c>", lambda e: self._copy_error_text(e))
        self.error_text.bind("<Control-C>", lambda e: self._copy_error_text(e))
        self.error_text.bind("<Control-Insert>", lambda e: self._copy_error_text(e))
        # Select all (ensure handler returns 'break')
        self.error_text.bind("<Control-a>", lambda e: (self.error_text.tag_add("sel", "1.0", "end") or "break"))
        self.error_text.bind("<Control-A>", lambda e: (self.error_text.tag_add("sel", "1.0", "end") or "break"))

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
                
            parsed_result = parse_schedule_block(raw)
            # parse_schedule_block now returns (events, errors)
            if isinstance(parsed_result, tuple) and len(parsed_result) == 2:
                events, errors = parsed_result
            else:
                events, errors = parsed_result, []

            self.events = events
            # If no events at all, show helpful hint (also show errors if any)
            if not self.events:
                self.canvas.delete("all")
                msg = "No events found. Make sure the format is:\nYYYY-MM-DD HH:MM HH:MM ROOM\nName1, Name2, ..."
                if errors:
                    err_text = "\n\nParse issues:\n" + "\n".join([f"Line {ln}: {m}" for ln, m in errors])
                    msg = msg + err_text
                    self.canvas.create_text(20, 20, anchor="nw", text=msg, fill=TEXT_COLOR["error"])
                else:
                    self.canvas.create_text(20, 20, anchor="nw", text=msg, fill=TEXT_COLOR["hint"])
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

        # Draw calendar and then populate the parse messages box (non-blocking)
        self.draw_calendar()

        # Populate error_text with parse issues (if any)
        try:
            self.error_text.configure(state=tk.NORMAL)
            self.error_text.delete("1.0", tk.END)
            if errors:
                err_lines = [f"Line {ln}: {msg}" for ln, msg in errors]
                display = "Parsing errors:\n" + "\n".join(err_lines)
                self.error_text.insert("1.0", display)
            else:
                self.error_text.insert("1.0", "No parsing errors detected.")
            # Make the box read-only but keep selection/copy bindings
            self.error_text.configure(state=tk.DISABLED)
        except Exception:
            # Fallback
            pass

    def _copy_error_text(self, event):
        """Copy selected text from the parsing messages box to the clipboard.

        If there's no selection, copy the full content.
        Returns "break" to stop default handling.
        """
        try:
            txt = self.error_text.get("sel.first", "sel.last")
        except tk.TclError:
            txt = self.error_text.get("1.0", "end").strip()
        if txt:
            try:
                self.clipboard_clear()
                self.clipboard_append(txt)
            except Exception:
                # ignore clipboard errors
                pass
        return "break"

    def on_export_one(self):
        if not self.by_person:
            messagebox.showwarning("No data", "Parse data first.")
            return
        person = self.person_var.get()
        if person == "(All)":
            messagebox.showinfo("Select person", "Please select a person to export.")
            return
        # Prefer a Save-As dialog so the user gets a prefilled filename and can
        # choose exactly where to save the single .ics file.
        # Include the title in the default filename (e.g. DL-lab1_First_Last.ics)
        safe_title = self.title_var.get().strip().replace(' ', '_')
        default_name = f"{safe_title}_{person.replace(' ', '_')}.ics"
        save_path = filedialog.asksaveasfilename(defaultextension=".ics",
                                                 filetypes=[("iCalendar", "*.ics")],
                                                 initialfile=default_name,
                                                 title=f"Export calendar for {person}")
        if not save_path:
            return
        # If the file already exists, ask user to confirm overwrite
        if os.path.exists(save_path):
            res = messagebox.askyesno("Overwrite?", f"The file {save_path} already exists. Overwrite?")
            if not res:
                return
        try:
            out = create_ics_for_person(person, self.by_person[person], self.title_var.get(), out_path=save_path)
            messagebox.showinfo("Done", f"Exported calendar for {person} to {out}")
        except (PermissionError, OSError) as e:
            messagebox.showerror("Export Error", f"Could not write file:\n{str(e)}\n\nMake sure you have write permissions and the file is not in use.")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export calendar:\n{str(e)}")

    def on_export_zip(self):
        if not self.by_person:
            messagebox.showwarning("No data", "Parse data first.")
            return
        zip_path = filedialog.asksaveasfilename(defaultextension=".zip", filetypes=[("ZIP files", "*.zip")])
        if not zip_path:
            return
        try:
            tmp = os.path.join(os.getcwd(), "_ics_tmp")
            os.makedirs(tmp, exist_ok=True)
            paths = [create_ics_for_person(p, evs, self.title_var.get(), tmp) for p, evs in self.by_person.items()]
            try:
                with zipfile.ZipFile(zip_path, "w") as zf:
                    for p in paths:
                        zf.write(p, arcname=os.path.basename(p))
                messagebox.showinfo("Done", f"Exported {len(paths)} calendars into {zip_path}")
            except (PermissionError, OSError) as e:
                messagebox.showerror("Export Error", f"Could not create zip file:\n{str(e)}\n\nMake sure you have write permissions and the file is not in use.")
            finally:
                # Clean up temp files even if zip creation fails
                for p in paths: 
                    try:
                        os.remove(p)
                    except OSError:
                        pass
                try:
                    os.rmdir(tmp)
                except OSError:
                    pass
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export calendars:\n{str(e)}")

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

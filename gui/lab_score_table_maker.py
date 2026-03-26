from collections import defaultdict
from io import StringIO
import re

import pandas as pd
import wx
import wx.html2

# Functions

group_header = "Grupa"


def read_table_from_csv(input: str):
    converters = {
        group_header: str,
        "ID": str,
        "JMBAG": str,
        "Prezime": str,
        "Ime": str,
    }
    df = pd.read_csv(
        StringIO(input),
        sep="\t",
        header=None,
        names=converters.keys(),
        converters=converters,
        index_col=False,
    )
    return df


def split_groups_by_room(df, sort_by_room=True):
    room_to_groups = defaultdict(lambda: [])
    for group, d in df.groupby(group_header):
        room = group.split(" ")[-1]
        if match := re.search(r"\d{4}-\d{2}-\d{2}", group):
            room = f"{room} {match.group(0)}"
        room_to_groups[room].append((group, d.drop(columns=[group_header])))
    if sort_by_room:
        rooms = sorted(room_to_groups.keys())
        room_to_groups = {room: room_to_groups[room] for room in rooms}
    return room_to_groups


def process_input_csv(input: str, num_tables_per_page=None, num_pages_per_sheet=None):
    df = read_table_from_csv(input)
    df["Bodovi"] = ""
    df["Komentar"] = ""
    df.set_index("ID", inplace=True)
    df = df.rename_axis(None)
    room_to_groups = split_groups_by_room(df)
    ntpp = num_tables_per_page  # None means auto (no forced page breaks)
    npps = num_pages_per_sheet  # None means auto (no sheet alignment)

    output_parts = [
        """<!DOCTYPE html>
        <html>
        <head>
        <meta charset="utf-8">
        <style>
        @media all { .page-break { display: none; } }
        @media print {
            .page-break {
                display: block;
                page-break-before: always;
            }
        }
        body {
            font-family: system-ui, sans-serif;
        }
        table, td, th {
            border: 1px solid #000;
            border-collapse: collapse;
            padding: 4px;
        }
        .no-break {
            page-break-inside: avoid;
            break-inside: avoid;
        }
        </style>
        </head>
        <body>""",
    ]
    for room, groups in room_to_groups.items():
        for i, (group, df) in enumerate(groups):
            dfs = df.style.set_properties(**{"text-align": "left"})
            dfs = dfs.set_table_styles([dict(selector="th", props=[("text-align", "left")])])
            dfs = dfs.set_properties(subset=["Komentar"], **{"width": "24em"})
            output_parts.append(f'\n<div class="no-break">')
            if ntpp is None:
                if i == 0:
                    output_parts.append(f"\n\n<h2> {room} </h2>")
            elif i % ntpp == 0:
                num_pages = (len(groups) + ntpp - 1) // ntpp
                output_parts.append(
                    f"\n\n<h2> {room} ({i//ntpp+1}/{num_pages}) </h2>"
                )
            output_parts.append(
                f"\n<h2> {group}</h2>"
                + dfs.to_html()
                + "</div>"
                + '<div class="page-break"></div>' * (ntpp is not None and (i + 1) % ntpp == 0),
            )
        if ntpp is None:
            num_filler_page_breaks = npps if npps is not None else 1
        else:
            num_pages = (len(groups) + ntpp - 1) // ntpp
            has_trailing_break = len(groups) % ntpp == 0
            if npps is None:
                num_filler_page_breaks = 0 if has_trailing_break else 1
            else:
                num_filler_pages = (npps - num_pages % npps) % npps
                num_filler_page_breaks = num_filler_pages + (0 if has_trailing_break else 1)
        for _ in range(num_filler_page_breaks):
            output_parts.append('<div class="page-break"></div>')
    for _ in range(num_filler_page_breaks):
        output_parts.pop()
    output_parts.append("\n</body>\n</html>")
    return "\n".join(output_parts)


# GUI


class MyFrame(wx.Frame):
    def __init__(self, parent, title):
        super(MyFrame, self).__init__(parent, title=title, size=(960, 480))
        self.output = ""

        panel = wx.Panel(self)

        vbox1 = wx.BoxSizer(wx.VERTICAL)
        panel.SetSizer(vbox1)

        hbox = wx.BoxSizer(wx.HORIZONTAL)
        vbox1.Add(
            hbox,
            proportion=1,
            flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP | wx.BOTTOM,
            border=10,
        )

        vbox_input = wx.BoxSizer(wx.VERTICAL)
        hbox.Add(vbox_input, proportion=1, flag=wx.EXPAND)

        input_label = wx.StaticText(panel, label="Input CSV: (?)")
        input_label.SetToolTip(
            wx.ToolTip(
                "Ferko → <predmet> → Grupe studenata (sve) → <grupa> (desni klik) → Eksport popisa (CSV)"
            )
        )
        vbox_input.Add(input_label, flag=wx.EXPAND)

        self.input_textarea = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        vbox_input.Add(self.input_textarea, proportion=1, flag=wx.EXPAND)

        hbox_options = wx.BoxSizer(wx.HORIZONTAL)
        vbox_input.Add(hbox_options, flag=wx.EXPAND | wx.TOP, border=5)

        num_tables_label = wx.StaticText(panel, label="Number of tables per page:")
        hbox_options.Add(num_tables_label, flag=wx.EXPAND | wx.LEFT, border=5)

        self.num_tables_per_page_selector = wx.Choice(panel, choices=["auto", "1", "2", "3", "4", "5", "6"])
        self.num_tables_per_page_selector.SetStringSelection("auto")
        hbox_options.Add(self.num_tables_per_page_selector, flag=wx.EXPAND | wx.LEFT, border=5)

        num_pages_label = wx.StaticText(panel, label="Number of pages per sheet:")
        hbox_options.Add(num_pages_label, flag=wx.EXPAND | wx.LEFT, border=5)

        self.num_pages_per_sheet_selector = wx.Choice(panel, choices=["1", "2", "3", "4", "5", "6"])
        self.num_pages_per_sheet_selector.SetStringSelection("1")
        hbox_options.Add(self.num_pages_per_sheet_selector, flag=wx.EXPAND | wx.LEFT, border=5)

        submit_button = wx.Button(panel, label="Submit")
        hbox_options.Add(submit_button, flag=wx.EXPAND | wx.LEFT, border=5)

        vbox_output = wx.BoxSizer(wx.VERTICAL)
        hbox.Add(vbox_output, proportion=1, flag=wx.EXPAND | wx.LEFT, border=10)

        input_label = wx.StaticText(panel, label="Output HTML:")
        vbox_output.Add(input_label, flag=wx.EXPAND)

        self.webview = wx.html2.WebView.New(panel)
        vbox_output.Add(self.webview, proportion=1, flag=wx.EXPAND)

        hbox_buttons = wx.BoxSizer(wx.HORIZONTAL)
        vbox_output.Add(hbox_buttons, flag=wx.EXPAND | wx.TOP, border=5)

        copy_button = wx.Button(panel, label="Copy")
        hbox_buttons.Add(copy_button, flag=wx.EXPAND)

        save_button = wx.Button(panel, label="Save")
        hbox_buttons.Add(save_button, flag=wx.EXPAND | wx.LEFT, border=5)

        submit_button.Bind(wx.EVT_BUTTON, self.on_submit_button_clicked)
        copy_button.Bind(wx.EVT_BUTTON, self.on_copy_button_clicked)
        save_button.Bind(wx.EVT_BUTTON, self.on_save_button_clicked)

    def on_submit_button_clicked(self, event):
        input_text = self.input_textarea.GetValue()
        try:
            def parse_selector(sel):
                s = sel.GetStringSelection()
                return None if s == "auto" else int(s)
            output = process_input_csv(
                input_text,
                num_tables_per_page=parse_selector(self.num_tables_per_page_selector),
                num_pages_per_sheet=parse_selector(self.num_pages_per_sheet_selector),
            )
            self.output = output
            self.webview.SetPage(output, "")
        except Exception as e:
            wx.MessageBox(str(e), "Error", wx.OK | wx.ICON_ERROR)

    def on_copy_button_clicked(self, event):
        try:
            if wx.TheClipboard.Open():
                data = wx.TextDataObject(self.output)
                wx.TheClipboard.SetData(data)
                wx.TheClipboard.Close()
            else:
                wx.MessageBox("Unable to open the clipboard", "Error", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            wx.MessageBox(str(e), "Error", wx.OK | wx.ICON_ERROR)

    def on_save_button_clicked(self, event):
        with wx.FileDialog(
            self,
            "Save HTML File",
            wildcard="HTML files (*.html)|*.html",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return
            pathname = fileDialog.GetPath()
            try:
                with open(pathname, "w", encoding="utf-8") as file:
                    file.write(self.output)
            except Exception as e:
                wx.MessageBox(str(e), "Error", wx.OK | wx.ICON_ERROR)
                raise e


class MyApp(wx.App):
    def OnInit(self):
        frame = MyFrame(None, title="Lab-table maker")
        frame.Show(True)
        return True


if __name__ == "__main__":
    app = MyApp()
    app.MainLoop()

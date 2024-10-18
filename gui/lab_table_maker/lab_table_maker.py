from collections import defaultdict
from io import StringIO
import re

import pandas as pd
import wx
import wx.html2

# Functions

group_header = "Grupa"


def read_table(input: str):
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


def split_groups(df):
    room_to_groups = defaultdict(lambda: [])
    for group, d in df.groupby(group_header):
        room = group.split(" ")[-1]
        if match := re.search(r"\d{4}-\d{2}-\d{2}", group):
            room = f"{match.group(0)} {room}"
        room_to_groups[room].append((group, d.drop(columns=[group_header])))
    return room_to_groups


def process_input(input: str, num_pages_per_sheet=1):
    df = read_table(input)
    df["Bodovi"] = ""
    df["Komentar"] = " " * 64
    df.set_index("ID", inplace=True)
    df = df.rename_axis(None)
    room_to_groups = split_groups(df)
    output_parts = [
        """
        <html>
        <style>
        @media all { .page-break { display: none; } }
        @media print { .page-break { display: block; page-break-before: always; } }
        table, td, th {
            border: 0.05rem solid #000;
            border-collapse: collapse;
            padding: 0.25rem;
        }
        </style>
        <body>"""
    ]
    for room, groups in room_to_groups.items():
        output_parts.append('<div class="page-break"></div>' + f"\n\n<h2> {room} </h2>")
        for group, df in groups:
            dfs = df.style.set_properties(**{"text-align": "left"})
            dfs = dfs.set_table_styles(
                [dict(selector="th", props=[("text-align", "left")])]
            )
            dfs.set_properties(subset=["Komentar"], **{"width": "24em"})
            output_parts.append(
                '<div class="page-break"></div>'
                + f"\n\n<h3> {group} </h3>"
                + dfs.to_html()
            )
        num_filler_pages = (
            num_pages_per_sheet - (len(groups) + 1) % num_pages_per_sheet
        ) % num_pages_per_sheet
        for _ in range(num_filler_pages):
            output_parts.append('<div class="page-break"></div>')
    for _ in range(num_filler_pages):
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

        input_label = wx.StaticText(panel, label="Input CSV:")
        vbox_input.Add(input_label, flag=wx.EXPAND)

        input_label.SetToolTip(wx.ToolTip('Ferko → <predmet> → Grupe studenata (sve) → <grupa> (desni klik) → Eksport popisa (CSV)'))

        self.input_textarea = wx.TextCtrl(panel, style=wx.TE_MULTILINE)
        vbox_input.Add(self.input_textarea, proportion=1, flag=wx.EXPAND)

        hbox_options = wx.BoxSizer(wx.HORIZONTAL)
        vbox_input.Add(hbox_options, flag=wx.EXPAND | wx.TOP, border=5)

        num_pages_label = wx.StaticText(panel, label="Number of pages per sheet:")
        hbox_options.Add(num_pages_label, flag=wx.EXPAND | wx.LEFT, border=5)

        self.num_pages_selector = num_pages_selector = wx.Choice(
            panel, choices=list(map(str, [1, 2, 3, 4, 6, 8, 9, 12, 16]))
        )
        num_pages_selector.SetStringSelection("1")
        hbox_options.Add(num_pages_selector, flag=wx.EXPAND | wx.LEFT, border=5)

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
            output = process_input(
                input_text,
                num_pages_per_sheet=int(self.num_pages_selector.GetStringSelection()),
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
                wx.MessageBox(
                    "Unable to open the clipboard", "Error", wx.OK | wx.ICON_ERROR
                )
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

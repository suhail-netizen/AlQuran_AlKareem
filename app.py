# Mushaf Overlay App - native desktop GUI.
# Generates the real Madinah mushaf (604 pages) with the user's chosen combination of theme colours
# and markers overlaid, as HTML pages only or as HTML + a merged PDF.

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from build_pdf import generate_html_pages, render_pdf_from_html


class App:
    def __init__(self, root):
        self.root = root
        root.title("Mushaf Overlay")
        root.geometry("480x470")
        root.resizable(False, False)

        frame = ttk.Frame(root, padding=20)
        frame.pack(fill='both', expand=True)

        row = 0
        self.themes_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Theme colours (each ayah tinted by its theme)",
                        variable=self.themes_var).grid(row=row, column=0, columnspan=2, sticky='w', pady=(0, 4))
        row += 1

        ttk.Separator(frame, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=(4, 10))
        row += 1

        ttk.Label(frame, text="Recitation markers (any combination):").grid(
            row=row, column=0, columnspan=2, sticky='w', pady=(0, 6))
        row += 1

        self.ramadan_var = tk.BooleanVar(value=False)
        self.standard_ruku_var = tk.BooleanVar(value=False)
        self.page_theme_ruku_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Ramadan rak'ah markers", variable=self.ramadan_var).grid(
            row=row, column=0, sticky='w', pady=2)
        ttk.Checkbutton(frame, text="Standard ruku (ركوع)", variable=self.standard_ruku_var).grid(
            row=row, column=1, sticky='w', pady=2)
        row += 1
        ttk.Checkbutton(frame, text="Page/theme ruku (candidate)", variable=self.page_theme_ruku_var).grid(
            row=row, column=0, sticky='w', pady=2)
        row += 1

        ttk.Separator(frame, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=(4, 10))
        row += 1

        ttk.Label(frame, text="Division markers (any combination):").grid(
            row=row, column=0, columnspan=2, sticky='w', pady=(0, 6))
        row += 1

        self.juz_var = tk.BooleanVar(value=False)
        self.hizb_var = tk.BooleanVar(value=False)
        self.nisf_var = tk.BooleanVar(value=False)
        self.rub_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Juz (الجزء)", variable=self.juz_var).grid(
            row=row, column=0, sticky='w', pady=2)
        ttk.Checkbutton(frame, text="Hizb (الحزب)", variable=self.hizb_var).grid(
            row=row, column=1, sticky='w', pady=2)
        row += 1
        ttk.Checkbutton(frame, text="Half-Hizb (نصف الحزب)", variable=self.nisf_var).grid(
            row=row, column=0, sticky='w', pady=2)
        ttk.Checkbutton(frame, text="Quarter (ربع الحزب)", variable=self.rub_var).grid(
            row=row, column=1, sticky='w', pady=2)
        row += 1

        ttk.Separator(frame, orient='horizontal').grid(row=row, column=0, columnspan=2, sticky='ew', pady=10)
        row += 1

        ttk.Label(frame, text="Output:").grid(row=row, column=0, sticky='w', pady=(0, 10))
        self.output_var = tk.StringVar(value="HTML + PDF")
        output_combo = ttk.Combobox(
            frame, textvariable=self.output_var, state='readonly',
            values=["HTML only", "HTML + PDF"],
        )
        output_combo.grid(row=row, column=1, sticky='ew', pady=(0, 10))
        row += 1

        ttk.Label(
            frame,
            text="Generates the full 604-page mushaf with the selected\nmarkers overlaid.",
            justify='left',
        ).grid(row=row, column=0, columnspan=2, sticky='w', pady=(0, 15))
        row += 1

        self.generate_btn = ttk.Button(frame, text="Generate & Save...", command=self.on_generate)
        self.generate_btn.grid(row=row, column=0, columnspan=2, sticky='ew')
        row += 1

        self.progress = ttk.Progressbar(frame, orient='horizontal', mode='determinate', maximum=604)
        self.progress.grid(row=row, column=0, columnspan=2, sticky='ew', pady=(15, 5))
        row += 1

        self.status_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.status_var).grid(row=row, column=0, columnspan=2, sticky='w')

        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

    def _enabled_divisions(self):
        divisions = set()
        if self.juz_var.get():
            divisions.add('juz')
        if self.hizb_var.get():
            divisions.add('hizb')
        if self.nisf_var.get():
            divisions.add('nisf')
        if self.rub_var.get():
            divisions.add('rub')
        return frozenset(divisions)

    def on_generate(self):
        show_themes = self.themes_var.get()
        show_ramadan = self.ramadan_var.get()
        show_standard_ruku = self.standard_ruku_var.get()
        show_page_theme_ruku = self.page_theme_ruku_var.get()
        divisions = self._enabled_divisions()
        want_pdf = self.output_var.get() == "HTML + PDF"

        if not show_themes and not show_ramadan and not show_standard_ruku and not show_page_theme_ruku and not divisions:
            messagebox.showwarning("Nothing selected", "Choose theme colours or at least one marker to include.")
            return

        name_parts = []
        if show_themes:
            name_parts.append('themes')
        if show_ramadan:
            name_parts.append('ramadan')
        if show_standard_ruku:
            name_parts.append('ruku')
        if show_page_theme_ruku:
            name_parts.append('pagetheme')
        name_parts.extend(sorted(divisions))
        base_name = 'mushaf_' + '_'.join(name_parts)

        if want_pdf:
            out_path = filedialog.asksaveasfilename(
                title="Save mushaf as",
                defaultextension=".pdf",
                filetypes=[("PDF file", "*.pdf")],
                initialfile=base_name + '.pdf',
            )
        else:
            out_path = filedialog.askdirectory(title="Choose a folder for the HTML pages")
        if not out_path:
            return

        self.generate_btn.state(['disabled'])
        self.progress['value'] = 0
        self.status_var.set("Generating...")

        def worker():
            try:
                def on_progress(phase, done, total):
                    self.root.after(0, self._update_progress, phase, done, total)

                if want_pdf:
                    html_dir = os.path.join(os.path.dirname(os.path.abspath(out_path)), '_build_html')
                    generate_html_pages(html_dir, show_ramadan, show_standard_ruku, show_page_theme_ruku,
                                       enabled_divisions=divisions, progress_callback=on_progress,
                                       show_themes=show_themes)
                    render_pdf_from_html(html_dir, out_path, progress_callback=on_progress)
                else:
                    generate_html_pages(out_path, show_ramadan, show_standard_ruku, show_page_theme_ruku,
                                       enabled_divisions=divisions, progress_callback=on_progress,
                                       show_themes=show_themes)
                self.root.after(0, self._on_done, out_path, None)
            except Exception as e:
                self.root.after(0, self._on_done, out_path, e)

        threading.Thread(target=worker, daemon=True).start()

    def _update_progress(self, phase, done, total):
        self.progress['value'] = done
        label = "Generating page" if phase == 'layout' else "Rendering PDF page"
        self.status_var.set(f"{label} {done} of {total}...")

    def _on_done(self, out_path, error):
        self.generate_btn.state(['!disabled'])
        if error:
            self.status_var.set("Failed.")
            messagebox.showerror("Error", str(error))
        else:
            self.status_var.set("Done.")
            messagebox.showinfo("Done", f"Saved to:\n{out_path}")


if __name__ == '__main__':
    root = tk.Tk()
    App(root)
    root.mainloop()

# Mushaf Overlay App - native desktop GUI.
# Generates the real Madinah mushaf (604 pages) with Ramadan rak'ah/night markers overlaid, and
# lets the user save the result as a PDF.

import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from build_pdf import build_pdf


class App:
    def __init__(self, root):
        self.root = root
        root.title("Mushaf Overlay - Ramadan Markers")
        root.geometry("480x250")
        root.resizable(False, False)

        frame = ttk.Frame(root, padding=20)
        frame.pack(fill='both', expand=True)

        ttk.Label(frame, text="Mushaf theme:").grid(row=0, column=0, sticky='w', pady=(0, 10))
        self.theme_var = tk.StringVar(value="standard1 (green)")
        theme_combo = ttk.Combobox(
            frame, textvariable=self.theme_var, state='readonly',
            values=["standard1 (green)"],
        )
        theme_combo.grid(row=0, column=1, sticky='ew', pady=(0, 10))

        ttk.Label(frame, text="Marker type:").grid(row=1, column=0, sticky='w', pady=(0, 10))
        self.mode_var = tk.StringVar(value="Ramadan (rak'ah markers)")
        mode_combo = ttk.Combobox(
            frame, textvariable=self.mode_var, state='readonly',
            values=["Ramadan (rak'ah markers)", "Standard ruku markers"],
        )
        mode_combo.grid(row=1, column=1, sticky='ew', pady=(0, 10))

        ttk.Label(
            frame,
            text="Generates the full 604-page mushaf with the selected\nmarkers overlaid, as a PDF.",
            justify='left',
        ).grid(row=2, column=0, columnspan=2, sticky='w', pady=(0, 15))

        self.generate_btn = ttk.Button(frame, text="Generate & Save...", command=self.on_generate)
        self.generate_btn.grid(row=3, column=0, columnspan=2, sticky='ew')

        self.progress = ttk.Progressbar(frame, orient='horizontal', mode='determinate', maximum=604)
        self.progress.grid(row=4, column=0, columnspan=2, sticky='ew', pady=(15, 5))

        self.status_var = tk.StringVar(value="")
        ttk.Label(frame, textvariable=self.status_var).grid(row=5, column=0, columnspan=2, sticky='w')

        frame.columnconfigure(1, weight=1)

    def on_generate(self):
        mode = 'ramadan' if self.mode_var.get().startswith('Ramadan') else 'standard'
        default_name = 'mushaf_ramadan_markers.pdf' if mode == 'ramadan' else 'mushaf_standard_ruku.pdf'

        out_path = filedialog.asksaveasfilename(
            title="Save mushaf as",
            defaultextension=".pdf",
            filetypes=[("PDF file", "*.pdf")],
            initialfile=default_name,
        )
        if not out_path:
            return

        self.generate_btn.state(['disabled'])
        self.progress['value'] = 0
        self.status_var.set("Generating...")

        def worker():
            try:
                def on_progress(done, total):
                    self.root.after(0, self._update_progress, done, total)

                build_pdf(out_path, mode=mode, progress_callback=on_progress)
                self.root.after(0, self._on_done, out_path, None)
            except Exception as e:
                self.root.after(0, self._on_done, out_path, e)

        threading.Thread(target=worker, daemon=True).start()

    def _update_progress(self, done, total):
        self.progress['value'] = done
        self.status_var.set(f"Rendering page {done} of {total}...")

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

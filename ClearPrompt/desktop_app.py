"""Native Windows ClearPrompt app. Uses the same local scanner and SQLite store."""
import csv
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from detector import RULES, inspect_text, redact_text
from storage import DEFAULT_SETTINGS, clear_audit, get_audit, get_scan_count, get_settings, initialize, record_scan, save_settings

BASE = Path(__file__).parent
DATABASE = str(BASE / "instance" / "clearprompt.sqlite3")
RULE_LABELS = [rule[0] for rule in RULES]
INK, RED, CREAM, PAPER, MUTED, YELLOW, GREEN = "#101010", "#e5252a", "#f4f0e7", "#fffdf8", "#827b70", "#f4d64f", "#247350"


class ClearPromptDesktop:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ClearPrompt — Prompt Security Desk")
        self.root.geometry("1220x900")
        self.root.minsize(940, 760)
        self.root.configure(bg=CREAM)
        initialize(DATABASE)
        self.settings = get_settings(DATABASE)
        self.policy = tk.StringVar(value=self.settings["policy"])
        self.detectors = {name: tk.BooleanVar(value=name in self.settings["enabled_detectors"]) for name in RULE_LABELS}
        self.selected_file: Path | None = None
        self._style()
        self._build()
        self._refresh_audit()

    def _style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Treeview", background=PAPER, fieldbackground=PAPER, foreground=INK,
                        rowheight=29, borderwidth=0, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background=INK, foreground="white",
                        font=("Consolas", 8, "bold"), relief="flat")
        style.map("Treeview", background=[("selected", "#f6d8d3")], foreground=[("selected", INK)])

    def _build(self):
        header = tk.Frame(self.root, bg=INK, height=62)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="C", bg=RED, fg="white", font=("Impact", 22), padx=12, pady=2).pack(side="left", padx=(24, 10), pady=10)
        tk.Label(header, text="CLEAR//PROMPT", bg=INK, fg="white", font=("Consolas", 16, "bold")).pack(side="left")
        tk.Label(header, text="LOCAL SECURITY DESK     ●  DESKTOP MODE", bg=INK, fg="#d7d0c4", font=("Consolas", 9)).pack(side="right", padx=25)

        viewport = tk.Frame(self.root, bg=CREAM)
        viewport.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(viewport, bg=CREAM, highlightthickness=0)
        scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        body = tk.Frame(self.canvas, bg=CREAM, padx=24, pady=17)
        body_window = self.canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(body_window, width=event.width))
        self.canvas.bind_all("<MouseWheel>", lambda event: self.canvas.yview_scroll(int(-event.delta / 120), "units"))
        tk.Label(body, text="PROTECT THE PROMPT.", bg=CREAM, fg=INK, font=("Impact", 35)).pack(anchor="w")
        tk.Label(body, text="Scan content locally. Choose a response. Keep sensitive data out of prompts.",
                 bg=CREAM, fg="#5f5a52", font=("Segoe UI", 10)).pack(anchor="w", pady=(1, 13))

        content = tk.Frame(body, bg=PAPER, highlightbackground=INK, highlightthickness=2, padx=16, pady=13)
        content.pack(fill="x")
        tk.Label(content, text="01 / CONTENT REVIEW", bg=PAPER, fg=RED, font=("Consolas", 9, "bold")).pack(anchor="w")
        tk.Label(content, text="Run a scan", bg=PAPER, fg=INK, font=("Impact", 22)).pack(anchor="w", pady=(1, 7))
        self.text = tk.Text(content, height=5, wrap="word", bg="#fffefa", fg=INK, insertbackground=RED,
                            font=("Consolas", 10), relief="solid", bd=1, padx=10, pady=8, undo=True)
        self.text.pack(fill="x")
        row = tk.Frame(content, bg=PAPER)
        row.pack(fill="x", pady=(7, 9))
        self.counter = tk.Label(row, text="0 / 1,000,000", bg=PAPER, fg=MUTED, font=("Consolas", 8))
        self.counter.pack(side="left")
        self.text.bind("<<Modified>>", self._count_text)
        self.text.edit_modified(False)
        self.file_label = tk.Label(row, text="TEXT STAYS ON THIS DEVICE", bg=PAPER, fg=MUTED, font=("Consolas", 8))
        self.file_label.pack(side="right")
        tk.Button(content, text="＋  OPEN A .TXT FILE", command=self._open_file, bg=CREAM, fg=INK,
                  activebackground="#e6dfd2", relief="solid", bd=1, font=("Consolas", 8, "bold"), padx=9, pady=5).pack(anchor="w")

        options = tk.Frame(body, bg=CREAM)
        options.pack(fill="x", pady=13)
        policy_box = tk.Frame(options, bg=CREAM)
        policy_box.pack(side="left", fill="both", expand=True)
        tk.Label(policy_box, text="RESPONSE POLICY", bg=CREAM, fg=INK, font=("Consolas", 9, "bold")).pack(anchor="w", pady=(0, 7))
        policy_row = tk.Frame(policy_box, bg=CREAM)
        policy_row.pack(anchor="w")
        for value, label, desc in [("warn", "WARN", "Flag and allow"), ("redact", "REDACT", "Mask matches"), ("block", "BLOCK", "Stop content")]:
            card = tk.Frame(policy_row, bg=PAPER, highlightbackground="#c8c0b5", highlightthickness=1, padx=10, pady=7)
            card.pack(side="left", padx=(0, 8))
            tk.Radiobutton(card, text=label, value=value, variable=self.policy, bg=PAPER, fg=INK,
                           activebackground=PAPER, selectcolor=RED, font=("Impact", 12)).pack(anchor="w")
            tk.Label(card, text=desc.upper(), bg=PAPER, fg=MUTED, font=("Consolas", 7)).pack(anchor="w", padx=4)

        settings = tk.Frame(body, bg=INK, padx=13, pady=10)
        settings.pack(fill="x", pady=(0, 12))
        tk.Label(settings, text="02 / DETECTION RULES", bg=INK, fg=YELLOW, font=("Consolas", 9, "bold")).pack(anchor="w")
        rule_grid = tk.Frame(settings, bg=INK)
        rule_grid.pack(fill="x", pady=(6, 3))
        for index, name in enumerate(RULE_LABELS):
            tk.Checkbutton(rule_grid, text=name.upper(), variable=self.detectors[name], bg=INK, fg="white",
                           activebackground=INK, activeforeground=YELLOW, selectcolor=RED,
                           font=("Consolas", 8), padx=5).grid(row=index // 4, column=index % 4, sticky="w", padx=(0, 8), pady=2)
        tk.Label(settings, text="CUSTOM KEYWORDS · ONE PER LINE", bg=INK, fg="#c7c0b5", font=("Consolas", 8)).pack(anchor="w", pady=(5, 4))
        self.keywords = tk.Text(settings, height=2, wrap="word", bg="#242321", fg="white", insertbackground=YELLOW,
                                font=("Consolas", 9), relief="flat", padx=7, pady=5)
        self.keywords.pack(fill="x")
        self.keywords.insert("1.0", "\n".join(self.settings["custom_keywords"]))
        tk.Button(settings, text="SAVE POLICY SETTINGS", command=self._save_settings,
                  bg=INK, fg=YELLOW, activebackground="#282522", relief="flat", font=("Consolas", 8, "bold")).pack(anchor="e", pady=(5, 0))

        actions = tk.Frame(body, bg=CREAM)
        actions.pack(fill="x")
        tk.Button(actions, text="SCAN CONTENT  ↗", command=self._scan, bg=RED, fg="white",
                  activebackground="#c21a24", relief="solid", bd=2, font=("Impact", 16), padx=16, pady=7).pack(side="left")
        tk.Button(actions, text="LOAD SAFE SAMPLE", command=self._load_sample,
                  bg=CREAM, fg=INK, activebackground="#e7dfd2", relief="solid", bd=1,
                  font=("Consolas", 8, "bold"), padx=10, pady=9).pack(side="left", padx=9)
        self.status = tk.Label(actions, text="READY · LOCAL PROCESSING", bg=CREAM, fg=GREEN, font=("Consolas", 8, "bold"))
        self.status.pack(side="right")

        self.result = tk.Frame(body, bg="#f7f2e7", highlightbackground=INK, highlightthickness=1, padx=12, pady=9)
        self.result.pack(fill="x", pady=(11, 0))
        self.result_label = tk.Label(self.result, text="NO SCAN YET", bg="#f7f2e7", fg=INK, font=("Impact", 15), anchor="w")
        self.result_label.pack(fill="x")
        self.findings_label = tk.Label(self.result, text="Run a scan to see policy results here.", bg="#f7f2e7", fg="#5f5a52", font=("Segoe UI", 9), justify="left", anchor="w")
        self.findings_label.pack(fill="x", pady=(3, 0))
        self.sanitized = tk.Text(self.result, height=3, wrap="word", bg="#fffefa", fg=INK, font=("Consolas", 9), relief="solid", bd=1)

        audit = tk.Frame(body, bg=PAPER, highlightbackground=INK, highlightthickness=2, padx=12, pady=9)
        audit.pack(fill="both", expand=True, pady=(13, 0))
        audit_head = tk.Frame(audit, bg=PAPER)
        audit_head.pack(fill="x", pady=(0, 7))
        tk.Label(audit_head, text="03 / RECENT ACTIVITY", bg=PAPER, fg=RED, font=("Consolas", 9, "bold")).pack(side="left")
        tk.Button(audit_head, text="EXPORT CSV ↓", command=self._export, bg=INK, fg="white", relief="flat", font=("Consolas", 8), padx=8, pady=4).pack(side="right", padx=(5, 0))
        tk.Button(audit_head, text="CLEAR LOG", command=self._clear, bg=PAPER, fg=INK, relief="solid", bd=1, font=("Consolas", 8), padx=8, pady=3).pack(side="right")
        columns = ("time", "policy", "outcome", "findings")
        self.table = ttk.Treeview(audit, columns=columns, show="headings", height=5)
        for key, title, width in [("time", "TIME (UTC)", 160), ("policy", "POLICY", 90), ("outcome", "OUTCOME", 110), ("findings", "FINDING TYPES", 500)]:
            self.table.heading(key, text=title)
            self.table.column(key, width=width, anchor="w")
        self.table.pack(fill="both", expand=True)
        tk.Label(body, text="CLEARPROMPT  ·  PYTHON + SQLITE  ·  NO NETWORK SERVER REQUIRED", bg=CREAM, fg=MUTED, font=("Consolas", 8)).pack(anchor="w", pady=(10, 0))

    def _count_text(self, _event=None):
        if self.text.edit_modified():
            count = len(self.text.get("1.0", "end-1c"))
            self.counter.config(text=f"{count:,} / 1,000,000")
            if count > 1_000_000:
                self.status.config(text="TEXT EXCEEDS 1 MB", fg=RED)
            self.text.edit_modified(False)

    def _get_settings(self):
        terms = [term.strip() for term in self.keywords.get("1.0", "end-1c").splitlines() if term.strip()]
        return {
            "policy": self.policy.get(),
            "enabled_detectors": [name for name, value in self.detectors.items() if value.get()],
            "custom_keywords": list(dict.fromkeys(term for term in terms if 2 <= len(term) <= 100))[:50],
        }

    def _save_settings(self):
        settings = self._get_settings()
        save_settings(DATABASE, settings)
        self.status.config(text="POLICY SETTINGS SAVED", fg=GREEN)
        self._refresh_audit()

    def _open_file(self):
        filename = filedialog.askopenfilename(title="Choose a text file", filetypes=[("Text files", "*.txt")])
        if not filename:
            return
        path = Path(filename)
        if path.stat().st_size > 1_000_000:
            messagebox.showerror("File too large", "Choose a .txt file under 1 MB.")
            return
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            messagebox.showerror("Can't read file", "This file is not valid UTF-8 text.")
            return
        self.selected_file = path
        self.text.delete("1.0", "end")
        self.text.insert("1.0", text)
        self.file_label.config(text=f"LOADED: {path.name}")
        self.status.config(text="TEXT FILE LOADED · READY TO SCAN", fg=GREEN)

    def _scan(self):
        text = self.text.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showinfo("Nothing to scan", "Paste text or open a .txt file first.")
            return
        if len(text) > 1_000_000:
            messagebox.showerror("Text too large", "Keep scanned text under 1 MB.")
            return
        settings = self._get_settings()
        save_settings(DATABASE, settings)
        findings = inspect_text(text, set(settings["enabled_detectors"]), settings["custom_keywords"])
        policy = settings["policy"]
        if findings and policy == "block":
            outcome = "Blocked"
            safe_text = None
            self.text.delete("1.0", "end")
        elif findings and policy == "redact":
            outcome = "Redacted"
            safe_text = redact_text(text, findings)
            self.text.delete("1.0", "end")
            self.text.insert("1.0", safe_text)
        elif findings:
            outcome, safe_text = "Warning", None
        else:
            outcome, safe_text = "Allowed", None
        record_scan(DATABASE, policy, outcome, findings)
        self._show_result(outcome, findings, safe_text)
        self.status.config(text=f"SCAN COMPLETE · {outcome.upper()}", fg=GREEN if outcome in {"Allowed", "Redacted"} else RED)
        self._refresh_audit()
        self.root.after_idle(lambda: self.canvas.yview_moveto(1.0))

    def _show_result(self, outcome, findings, safe_text):
        self.result.config(bg="#fce8e3" if outcome == "Blocked" else "#fff3d9" if outcome == "Warning" else "#e9f3e9")
        self.result_label.config(text=f"{outcome.upper()}   ·   {len(findings)} FINDING{'S' if len(findings) != 1 else ''}", bg=self.result.cget("bg"))
        details = "\n".join(f"• {item['type']} — {item['explanation']}" for item in findings) if findings else "No enabled rules matched this content. It is ready to use."
        if outcome == "Blocked":
            details += "\nContent was stopped by the selected policy."
        self.findings_label.config(text=details, bg=self.result.cget("bg"))
        self.sanitized.pack_forget()
        if safe_text is not None:
            self.sanitized.delete("1.0", "end")
            self.sanitized.insert("1.0", "SANITIZED TEXT\n" + safe_text)
            self.sanitized.pack(fill="x", pady=(7, 0))

    def _load_sample(self):
        self.selected_file = None
        self.file_label.config(text="SAFE SAMPLE LOADED")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", "Hi, please send the customer update to priya.shah@example.com. Call me at (415) 555-0138.")
        self.text.focus_set()

    def _refresh_audit(self):
        for item in self.table.get_children():
            self.table.delete(item)
        for event in get_audit(DATABASE, limit=50):
            when = datetime.fromisoformat(event["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
            finding_types = ", ".join(event["finding_types"]) if event["finding_types"] else "None"
            self.table.insert("", "end", values=(when, event["policy"].upper(), event["outcome"].upper(), finding_types))
        total = get_scan_count(DATABASE)
        self.root.title(f"ClearPrompt — Prompt Security Desk · {total} scans")

    def _export(self):
        filename = filedialog.asksaveasfilename(title="Export ClearPrompt audit", defaultextension=".csv",
                                                 initialfile="clearprompt-audit.csv", filetypes=[("CSV files", "*.csv")])
        if not filename:
            return
        with open(filename, "w", newline="", encoding="utf-8-sig") as output:
            writer = csv.writer(output)
            writer.writerow(["timestamp_utc", "policy", "outcome", "finding_count", "finding_types"])
            for event in get_audit(DATABASE, limit=10000):
                writer.writerow([event["timestamp"], event["policy"], event["outcome"], event["finding_count"], "; ".join(event["finding_types"])])
        self.status.config(text="AUDIT CSV EXPORTED", fg=GREEN)

    def _clear(self):
        if not messagebox.askyesno("Clear local audit", "Permanently clear the audit history stored on this device?"):
            return
        clear_audit(DATABASE)
        self._refresh_audit()
        self.status.config(text="LOCAL AUDIT CLEARED", fg=GREEN)


if __name__ == "__main__":
    window = tk.Tk()
    ClearPromptDesktop(window)
    window.mainloop()

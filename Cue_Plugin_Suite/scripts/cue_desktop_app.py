from __future__ import annotations

import json
import os
import re
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

# Add repository root to system path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class ScrollableFrame(ttk.Frame):
    """A standard Tkinter scrollable frame using Canvas and Scrollbar."""
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0, bg="#0f172a")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas, style="TFrame")

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind mousewheel scrolling safely
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        self.canvas.bind("<Enter>", lambda _: self.canvas.bind_all("<MouseWheel>", _on_mousewheel))
        self.canvas.bind("<Leave>", lambda _: self.canvas.unbind_all("<MouseWheel>"))

        # Bind canvas resize to frame width
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _on_canvas_configure(self, event):
        # Keep internal frame matched to canvas width
        self.canvas.itemconfig(self.canvas_window, width=event.width)


class CueDesktopApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Cue Creator Intelligence Cockpit")
        self.root.geometry("1200x820")
        self.root.minsize(900, 600)

        # Setup custom dark themes/styles
        self.setup_styles()

        # Track exporter values
        self.current_export_path = None

        # Main Layout: Left control panel, Right results panel
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left Frame (Inputs & Plugins)
        left_frame = ttk.Frame(paned, padding=15, style="TFrame")
        left_frame.pack(fill=tk.BOTH, expand=True)
        paned.add(left_frame, weight=1)

        # Right Frame (Results Dashboard)
        right_frame = ttk.Frame(paned, padding=15, style="TFrame")
        right_frame.pack(fill=tk.BOTH, expand=True)
        paned.add(right_frame, weight=3)

        # --- LEFT PANE WIDGETS ---
        header_label = ttk.Label(left_frame, text="ANALYSIS CONFIG", style="Header.TLabel")
        header_label.pack(anchor="w", pady=(0, 15))

        # Inputs Form
        form_frame = ttk.Frame(left_frame, style="TFrame")
        form_frame.pack(fill=tk.X, pady=(0, 15))

        # Topic
        ttk.Label(form_frame, text="Topic or RSS Feed URL").pack(anchor="w", pady=(5, 2))
        self.topic_entry = ttk.Entry(form_frame, font=("Inter", 10))
        self.topic_entry.insert(0, "Michigan redistricting")
        self.topic_entry.pack(fill=tk.X, pady=(0, 10))

        # Target Platform
        ttk.Label(form_frame, text="Target Platform").pack(anchor="w", pady=(5, 2))
        self.platform_combo = ttk.Combobox(form_frame, values=["podcast", "youtube"], state="readonly", font=("Inter", 10))
        self.platform_combo.set("podcast")
        self.platform_combo.pack(fill=tk.X, pady=(0, 10))

        # Tenant ID
        ttk.Label(form_frame, text="Tenant ID").pack(anchor="w", pady=(5, 2))
        self.tenant_entry = ttk.Entry(form_frame, font=("Inter", 10))
        self.tenant_entry.insert(0, "local-test-tenant")
        self.tenant_entry.pack(fill=tk.X, pady=(0, 10))

        # User ID
        ttk.Label(form_frame, text="User ID").pack(anchor="w", pady=(5, 2))
        self.user_entry = ttk.Entry(form_frame, font=("Inter", 10))
        self.user_entry.insert(0, "local-test-user")
        self.user_entry.pack(fill=tk.X, pady=(0, 10))

        # Workspace ID
        ttk.Label(form_frame, text="Workspace ID").pack(anchor="w", pady=(5, 2))
        self.workspace_entry = ttk.Entry(form_frame, font=("Inter", 10))
        self.workspace_entry.insert(0, "local-test-workspace")
        self.workspace_entry.pack(fill=tk.X, pady=(0, 10))

        # Debug Checkbox
        self.debug_var = tk.BooleanVar(value=False)
        self.debug_check = ttk.Checkbutton(form_frame, text="Enable Debug Stacktraces", variable=self.debug_var)
        self.debug_check.pack(anchor="w", pady=10)

        # Action Buttons
        btn_frame = ttk.Frame(left_frame, style="TFrame")
        btn_frame.pack(fill=tk.X, pady=(0, 15))

        self.analyze_btn = ttk.Button(btn_frame, text="Run Cue Analysis", style="Primary.TButton", command=self.on_analyze_click)
        self.analyze_btn.pack(fill=tk.X, pady=(0, 5))

        self.clear_btn = ttk.Button(btn_frame, text="Clear Config & Dashboard", style="TButton", command=self.on_clear_click)
        self.clear_btn.pack(fill=tk.X)

        # System Status
        self.status_frame = ttk.Frame(left_frame, style="TFrame")
        self.status_frame.pack(fill=tk.X, pady=(0, 15))
        self.status_indicator = tk.Label(self.status_frame, text="●", foreground="#94a3b8", bg="#0f172a", font=("Inter", 12))
        self.status_indicator.pack(side="left", padx=(0, 5))
        self.status_text = ttk.Label(self.status_frame, text="System Ready", font=("Inter", 10, "bold"))
        self.status_text.pack(side="left")

        # Plugin Configuration Status
        ttk.Separator(left_frame, orient="horizontal").pack(fill=tk.X, pady=10)
        
        plugin_header_frame = ttk.Frame(left_frame, style="TFrame")
        plugin_header_frame.pack(fill=tk.X, pady=(5, 5))
        ttk.Label(plugin_header_frame, text="ACTIVE SYSTEM PLUGINS", style="Section.TLabel").pack(side="left")
        
        self.refresh_plugins_btn = ttk.Button(plugin_header_frame, text="Refresh", style="TButton", width=8, command=self.load_plugins_status)
        self.refresh_plugins_btn.pack(side="right")

        # ScrolledText to show plugins configurations in the left panel
        self.plugins_status_text = scrolledtext.ScrolledText(
            left_frame, height=8, font=("Consolas", 9), bg="#1e293b", fg="#f1f5f9",
            insertbackground="#f1f5f9", state=tk.DISABLED, highlightthickness=1, highlightbackground="#374151", bd=0
        )
        self.plugins_status_text.pack(fill=tk.BOTH, expand=True)
        # Tag styling for plugins status
        self.plugins_status_text.tag_config("active", foreground="#10b981", font=("Consolas", 9, "bold"))
        self.plugins_status_text.tag_config("skipped", foreground="#f59e0b", font=("Consolas", 9, "bold"))
        self.plugins_status_text.tag_config("disabled", foreground="#9ca3af")
        self.plugins_status_text.tag_config("error", foreground="#ef4444", font=("Consolas", 9, "bold"))
        self.plugins_status_text.tag_config("detail", foreground="#94a3b8")

        # --- RIGHT PANE WIDGETS ---
        right_header = ttk.Frame(right_frame, style="TFrame")
        right_header.pack(fill=tk.X, pady=(0, 10))
        self.results_title = ttk.Label(right_header, text="INTELLIGENCE REPORT", style="Header.TLabel")
        self.results_title.pack(side="left")

        # Export folder trigger
        self.export_frame = ttk.Frame(right_frame, style="TFrame")
        self.export_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(self.export_frame, text="Export File:", font=("Inter", 9, "bold"), foreground="#94a3b8").pack(side="left", padx=(0, 5))
        self.export_path_label = ttk.Label(self.export_frame, text="No active run", font=("Inter", 9, "italic"), foreground="#94a3b8")
        self.export_path_label.pack(side="left", fill=tk.X, expand=True)

        self.open_export_btn = ttk.Button(self.export_frame, text="Open Folder", style="TButton", state=tk.DISABLED, command=self.on_open_folder_click)
        self.open_export_btn.pack(side="right", padx=(5, 0))
        self.copy_path_btn = ttk.Button(self.export_frame, text="Copy Path", style="TButton", state=tk.DISABLED, command=self.on_copy_path_click)
        self.copy_path_btn.pack(side="right")

        # Scrollable container for analysis results
        self.scrollable = ScrollableFrame(right_frame)
        self.scrollable.pack(fill=tk.BOTH, expand=True)
        results_container = self.scrollable.scrollable_frame

        # Placeholder message
        self.placeholder_label = ttk.Label(
            results_container,
            text="\n\n\nNo report loaded. Configure inputs and click 'Run Cue Analysis'.",
            font=("Inter", 11, "italic"), foreground="#94a3b8", justify="center"
        )
        self.placeholder_label.pack(pady=40, anchor="center")

        # Score cards container
        self.cards_frame = ttk.Frame(results_container, style="TFrame")
        
        # Opportunity Card
        self.opp_card = ttk.Frame(self.cards_frame, style="Card.TFrame", padding=10)
        self.opp_card.grid(row=0, column=0, sticky="nsew", padx=5)
        ttk.Label(self.opp_card, text="OPPORTUNITY SCORE", style="CardLabel.TLabel").pack(anchor="w")
        self.opp_val = ttk.Label(self.opp_card, text="--", style="CardScore.TLabel")
        self.opp_val.pack(anchor="w", pady=2)
        self.opp_grade = ttk.Label(self.opp_card, text="--", style="CardGrade.TLabel")
        self.opp_grade.pack(anchor="w")
        self.opp_exp = ttk.Label(self.opp_card, text="--", font=("Inter", 9), wraplength=220, justify="left", foreground="#94a3b8")
        self.opp_exp.pack(anchor="w", pady=5)

        # Platform Readiness Card
        self.read_card = ttk.Frame(self.cards_frame, style="Card.TFrame", padding=10)
        self.read_card.grid(row=0, column=1, sticky="nsew", padx=5)
        ttk.Label(self.read_card, text="PLATFORM READINESS", style="CardLabel.TLabel").pack(anchor="w")
        self.read_val = ttk.Label(self.read_card, text="--", style="CardScore.TLabel")
        self.read_val.pack(anchor="w", pady=2)
        self.read_grade = ttk.Label(self.read_card, text="--", style="CardGrade.TLabel")
        self.read_grade.pack(anchor="w")
        self.read_exp = ttk.Label(self.read_card, text="--", font=("Inter", 9), wraplength=220, justify="left", foreground="#94a3b8")
        self.read_exp.pack(anchor="w", pady=5)

        # Confidence Card
        self.conf_card = ttk.Frame(self.cards_frame, style="Card.TFrame", padding=10)
        self.conf_card.grid(row=0, column=2, sticky="nsew", padx=5)
        ttk.Label(self.conf_card, text="CONFIDENCE SCORE", style="CardLabel.TLabel").pack(anchor="w")
        self.conf_val = ttk.Label(self.conf_card, text="--", style="CardScore.TLabel")
        self.conf_val.pack(anchor="w", pady=2)
        self.conf_grade = ttk.Label(self.conf_card, text="--", style="CardGrade.TLabel")
        self.conf_grade.pack(anchor="w")
        self.conf_exp = ttk.Label(self.conf_card, text="--", font=("Inter", 9), wraplength=220, justify="left", foreground="#94a3b8")
        self.conf_exp.pack(anchor="w", pady=5)

        self.cards_frame.columnconfigure(0, weight=1)
        self.cards_frame.columnconfigure(1, weight=1)
        self.cards_frame.columnconfigure(2, weight=1)

        # Recommendations & Creator Output Columns
        self.details_frame = ttk.Frame(results_container, style="TFrame")
        
        # Recommendations Frame
        self.recs_frame = ttk.Frame(self.details_frame, style="TFrame")
        self.recs_frame.pack(side="left", fill=tk.BOTH, expand=True, padx=(0, 10))
        ttk.Label(self.recs_frame, text="Key Recommendations & Insights", style="Section.TLabel").pack(anchor="w", pady=(0, 5))
        self.recs_text = scrolledtext.ScrolledText(
            self.recs_frame, height=8, font=("Inter", 9), bg="#1e293b", fg="#f1f5f9",
            state=tk.DISABLED, bd=0, highlightthickness=1, highlightbackground="#374151"
        )
        self.recs_text.pack(fill=tk.BOTH, expand=True)

        # Creator Output Frame
        self.output_frame = ttk.Frame(self.details_frame, style="Card.TFrame", padding=12)
        self.output_frame.pack(side="right", fill=tk.BOTH, expand=True, padx=(10, 0))
        ttk.Label(self.output_frame, text="CREATOR GENERATED OUTPUT", style="CardLabel.TLabel").pack(anchor="w", pady=(0, 5))
        
        ttk.Label(self.output_frame, text="Episode Title Idea:", font=("Inter", 9, "bold")).pack(anchor="w")
        self.out_title = ttk.Label(self.output_frame, text="No title generated", font=("Inter", 10, "bold"), wraplength=300)
        self.out_title.pack(anchor="w", pady=(0, 8))

        ttk.Label(self.output_frame, text="Description Hook (150 words):", font=("Inter", 9, "bold")).pack(anchor="w")
        self.out_desc = tk.Text(
            self.output_frame, height=5, font=("Inter", 9), bg="#1e293b", fg="#94a3b8",
            bd=0, highlightthickness=0, wrap="word"
        )
        self.out_desc.insert("1.0", "No description generated.")
        self.out_desc.config(state=tk.DISABLED)
        self.out_desc.pack(fill=tk.BOTH, expand=True)

        # Content Gaps Frame
        self.gaps_frame = ttk.Frame(results_container, style="TFrame")
        ttk.Label(self.gaps_frame, text="Identified Content Gaps", style="Section.TLabel").pack(anchor="w", pady=(0, 5))
        self.gaps_text = scrolledtext.ScrolledText(
            self.gaps_frame, height=6, font=("Inter", 9), bg="#1e293b", fg="#f1f5f9",
            state=tk.DISABLED, bd=0, highlightthickness=1, highlightbackground="#374151"
        )
        self.gaps_text.pack(fill=tk.BOTH, expand=True)
        self.gaps_text.tag_config("gap_topic", foreground="#818cf8", font=("Inter", 9, "bold"))
        self.gaps_text.tag_config("gap_detail", foreground="#94a3b8")
        self.gaps_text.tag_config("gap_angle", foreground="#14b8a6", font=("Inter", 9, "italic"))

        # Plugin Run Status Frame
        self.plugins_run_frame = ttk.Frame(results_container, style="TFrame")
        ttk.Label(self.plugins_run_frame, text="Plugin Execution Summary", style="Section.TLabel").pack(anchor="w", pady=(0, 5))
        self.plugins_run_text = scrolledtext.ScrolledText(
            self.plugins_run_frame, height=4, font=("Consolas", 9), bg="#1e293b", fg="#f1f5f9",
            state=tk.DISABLED, bd=0, highlightthickness=1, highlightbackground="#374151"
        )
        self.plugins_run_text.pack(fill=tk.BOTH, expand=True)
        self.plugins_run_text.tag_config("active", foreground="#10b981", font=("Consolas", 9, "bold"))
        self.plugins_run_text.tag_config("skipped", foreground="#f59e0b", font=("Consolas", 9, "bold"))
        self.plugins_run_text.tag_config("error", foreground="#ef4444", font=("Consolas", 9, "bold"))

        # Raw Response Frame (Collapsible details)
        self.raw_frame = ttk.Frame(results_container, style="TFrame")
        
        self.show_raw_var = tk.BooleanVar(value=False)
        self.raw_toggle = ttk.Checkbutton(self.raw_frame, text="Show Raw JSON Response", variable=self.show_raw_var, command=self.toggle_raw_json)
        self.raw_toggle.pack(anchor="w", pady=5)
        
        self.raw_text = scrolledtext.ScrolledText(
            self.raw_frame, height=12, font=("Consolas", 9), bg="#0b0f19", fg="#a7f3d0",
            insertbackground="#a7f3d0", state=tk.DISABLED, highlightthickness=1, highlightbackground="#374151", bd=0
        )

        # Load initial plugins
        self.load_plugins_status()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Color definitions
        bg_dark = "#0b0f19"
        bg_panel = "#0f172a"
        bg_card = "#1e293b"
        text_light = "#f3f4f6"
        border_color = "#374151"
        accent_teal = "#14b8a6"
        accent_hover = "#0d9488"
        text_muted = "#9ca3af"

        style.configure(".", background=bg_panel, foreground=text_light, fieldbackground=bg_card, bordercolor=border_color)
        style.configure("TFrame", background=bg_panel)
        style.configure("TLabel", background=bg_panel, foreground=text_light, font=("Inter", 9))
        style.configure("Header.TLabel", font=("Inter", 14, "bold"), foreground=accent_teal, background=bg_panel)
        style.configure("Section.TLabel", font=("Inter", 11, "bold"), foreground="#818cf8", background=bg_panel)
        
        # Inputs & Entries
        style.configure("TEntry", fieldbackground=bg_card, foreground=text_light, insertcolor=text_light, bordercolor=border_color)
        style.configure("TCombobox", fieldbackground=bg_card, foreground=text_light, selectbackground=bg_card, selectforeground=text_light)
        style.configure("TCheckbutton", background=bg_panel, foreground=text_light)

        # Scorecard
        style.configure("Card.TFrame", background=bg_card, borderwidth=1, relief="solid")
        style.configure("CardLabel.TLabel", background=bg_card, foreground=text_muted, font=("Inter", 8, "bold"))
        style.configure("CardScore.TLabel", background=bg_card, foreground=text_light, font=("Inter", 24, "bold"))
        style.configure("CardGrade.TLabel", background=bg_card, foreground=accent_teal, font=("Inter", 9, "bold"))

        # Buttons
        style.configure("TButton", background=bg_card, foreground=text_light, borderwidth=1, font=("Inter", 9, "bold"), focuscolor="")
        style.map("TButton", background=[("active", "#334155"), ("disabled", bg_panel)], foreground=[("disabled", "#64748b")])
        style.configure("Primary.TButton", background=accent_teal, foreground="#ffffff")
        style.map("Primary.TButton", background=[("active", accent_hover), ("disabled", bg_panel)], foreground=[("disabled", "#64748b")])

    def load_plugins_status(self):
        """Fetch system configurations and plug-ins directly from router."""
        self.plugins_status_text.config(state=tk.NORMAL)
        self.plugins_status_text.delete("1.0", tk.END)
        self.plugins_status_text.insert(tk.END, "Checking system plugins status...\n", "detail")
        self.plugins_status_text.config(state=tk.DISABLED)

        tenant = self.tenant_entry.get().strip()
        user = self.user_entry.get().strip()
        workspace = self.workspace_entry.get().strip()
        debug_val = self.debug_var.get()

        def fetch():
            try:
                from src.api.router import CueApiRouter
                from src.core.types.models import CueRequestContext

                router = CueApiRouter()
                context = CueRequestContext(
                    tenant_id=tenant or "local-test-tenant",
                    user_id=user or "local-test-user",
                    workspace_id=workspace or None,
                    roles=["api"],
                    debug=debug_val,
                )
                data = router.plugin_status(context=context)
                plugins = data.get("plugins", [])
                
                self.root.after(0, self.display_plugins_status, plugins)
            except Exception as exc:
                self.root.after(0, self.display_plugins_error, str(exc))

        threading.Thread(target=fetch, daemon=True).start()

    def display_plugins_status(self, plugins):
        self.plugins_status_text.config(state=tk.NORMAL)
        self.plugins_status_text.delete("1.0", tk.END)
        
        if not plugins:
            self.plugins_status_text.insert(tk.END, "No plugins loaded.\n", "detail")
            self.plugins_status_text.config(state=tk.DISABLED)
            return

        for p in plugins:
            pid = p.get("plugin_id", "").upper()
            name = p.get("plugin_name", pid)
            enabled = p.get("enabled", False)
            configured = p.get("configured", False)
            last_run_status = p.get("last_run_status")
            if last_run_status is None:
                last_run_status = "NOT RUN"
            msg = p.get("message", "")
            missing_vars = p.get("missing_environment_variables", [])

            status_str = "ACTIVE" if (enabled and last_status_is_active(last_run_status)) else last_run_status.upper()
            tag = "disabled"
            if enabled:
                tag = "active" if status_str == "ACTIVE" else "skipped"
            if missing_vars:
                status_str = "UNCONFIGURED"
                tag = "skipped"

            self.plugins_status_text.insert(tk.END, f"• {name} [{status_str}]\n", tag)
            if missing_vars:
                self.plugins_status_text.insert(tk.END, f"  Missing env: {', '.join(missing_vars)}\n", "detail")
            if msg:
                self.plugins_status_text.insert(tk.END, f"  {msg}\n", "detail")
        
        self.plugins_status_text.config(state=tk.DISABLED)

    def display_plugins_error(self, error_msg):
        self.plugins_status_text.config(state=tk.NORMAL)
        self.plugins_status_text.delete("1.0", tk.END)
        self.plugins_status_text.insert(tk.END, f"Error reading plugins:\n{error_msg}\n", "error")
        self.plugins_status_text.config(state=tk.DISABLED)

    def on_analyze_click(self):
        topic = self.topic_entry.get().strip()
        if not topic:
            messagebox.showerror("Validation Error", "Please enter a topic or RSS feed URL to analyze.")
            return

        # Loading states
        self.status_indicator.config(foreground="orange")
        self.status_text.config(text="Analyzing...", foreground="orange")
        self.analyze_btn.config(state=tk.DISABLED)
        self.clear_btn.config(state=tk.DISABLED)
        self.refresh_plugins_btn.config(state=tk.DISABLED)
        
        # Clear previous result layout & placeholder
        self.placeholder_label.pack_forget()
        self.hide_results_widgets()

        platform = self.platform_combo.get()
        tenant = self.tenant_entry.get().strip()
        user = self.user_entry.get().strip()
        workspace = self.workspace_entry.get().strip()
        debug_val = self.debug_var.get()

        def analyze_thread():
            try:
                from src.api.router import CueApiRouter
                from src.core.types.models import CueRequestContext

                router = CueApiRouter()
                context = CueRequestContext(
                    tenant_id=tenant or "local-test-tenant",
                    user_id=user or "local-test-user",
                    workspace_id=workspace or None,
                    roles=["api"],
                    debug=debug_val,
                )

                payload = {"targetPlatform": platform}
                if topic.startswith("http://") or topic.startswith("https://") or ".xml" in topic or "/feed" in topic:
                    payload["rssUrl"] = topic
                    result = router.analyze_rss(payload, context=context)
                else:
                    payload["topic"] = topic
                    result = router.analyze_topic(payload, context=context)

                self.root.after(0, self.display_analysis_results, result)
            except Exception as exc:
                import traceback
                trace = traceback.format_exc()
                self.root.after(0, self.display_analysis_error, str(exc), trace if debug_val else None)

        threading.Thread(target=analyze_thread, daemon=True).start()

    def display_analysis_results(self, result):
        # Update System Status
        self.status_indicator.config(foreground="#10b981")
        self.status_text.config(text="Analysis Complete", foreground="#10b981")
        self.analyze_btn.config(state=tk.NORMAL)
        self.clear_btn.config(state=tk.NORMAL)
        self.refresh_plugins_btn.config(state=tk.NORMAL)

        # Show panels
        self.show_results_widgets()

        # Extract values
        topic = result.get("primary_topic", "Intelligence Report")
        self.results_title.config(text=f"REPORT: {topic.upper()}")
        
        run_id = result.get("run_id", "N/A")
        export_path = result.get("export_paths", {}).get("json", "")
        self.current_export_path = export_path
        
        if export_path:
            self.export_path_label.config(text=export_path)
            self.open_export_btn.config(state=tk.NORMAL)
            self.copy_path_btn.config(state=tk.NORMAL)
        else:
            self.export_path_label.config(text="No export generated.")
            self.open_export_btn.config(state=tk.DISABLED)
            self.copy_path_btn.config(state=tk.DISABLED)

        # Render Score Cards
        cards = result.get("score_cards", [])
        opp_card_data = find_card_by_label(cards, "Opportunity") or {"score": result.get("scores", {}).get("opportunity", 0), "grade": "Reported", "short_explanation": "Direct opportunity analysis."}
        read_card_data = find_card_by_label(cards, "Platform Readiness") or {"score": result.get("scores", {}).get("platform_readiness", 0), "grade": "Reported", "short_explanation": "Direct readiness suit."}
        conf_card_data = find_card_by_label(cards, "Confidence") or {"score": result.get("scores", {}).get("confidence", 0), "grade": "Reported", "short_explanation": "Direct confidence assessment."}

        self.render_card_widget(self.opp_val, self.opp_grade, self.opp_exp, opp_card_data)
        self.render_card_widget(self.read_val, self.read_grade, self.read_exp, read_card_data)
        self.render_card_widget(self.conf_val, self.conf_grade, self.conf_exp, conf_card_data)

        # Render Recommendations
        recs = result.get("top_recommendations", [])
        self.recs_text.config(state=tk.NORMAL)
        self.recs_text.delete("1.0", tk.END)
        if recs:
            for r in recs:
                self.recs_text.insert(tk.END, f"• {r}\n\n")
        else:
            self.recs_text.insert(tk.END, "No specific recommendations returned.")
        self.recs_text.config(state=tk.DISABLED)

        # Render Creator Outputs
        outputs = result.get("recommended_outputs", {})
        title_idea = outputs.get("episodeTitle", "No title generated")
        desc_idea = outputs.get("descriptionOpening150Words", "No description hook generated.")
        tags_idea = ", ".join(outputs.get("tags", []))

        self.out_title.config(text=title_idea)
        
        self.out_desc.config(state=tk.NORMAL)
        self.out_desc.delete("1.0", tk.END)
        self.out_desc.insert("1.0", desc_idea)
        if tags_idea:
            self.out_desc.insert(tk.END, f"\n\nTags: {tags_idea}")
        self.out_desc.config(state=tk.DISABLED)

        # Render Content Gaps
        gaps = result.get("content_gaps", [])
        self.gaps_text.config(state=tk.NORMAL)
        self.gaps_text.delete("1.0", tk.END)
        if gaps:
            for g in gaps:
                gap_topic = "Unknown Topic"
                reason = "No reasoning supplied."
                angle = ""
                confidence = None

                if isinstance(g, str):
                    gap_topic = g
                elif g and isinstance(g, dict):
                    gap_topic = g.get("gap_topic") or g.get("topic") or "Unknown Topic"
                    reason = g.get("reason") or g.get("description") or "No reasoning supplied."
                    angle = g.get("suggested_angle") or g.get("angle") or ""
                    confidence = g.get("confidence")

                conf_suffix = f" (Confidence: {confidence}%)" if confidence else ""
                self.gaps_text.insert(tk.END, f"Topic: {gap_topic}{conf_suffix}\n", "gap_topic")
                self.gaps_text.insert(tk.END, f"Evidence: {reason}\n", "gap_detail")
                if angle:
                    self.gaps_text.insert(tk.END, f"Suggested Angle: {angle}\n", "gap_angle")
                self.gaps_text.insert(tk.END, "\n")
        else:
            self.gaps_text.insert(tk.END, "No content gaps reported for this topic.")
        self.gaps_text.config(state=tk.DISABLED)

        # Render Run Plugins Breakdown
        run_plugins = result.get("signal_summary", {}).get("plugins", [])
        self.plugins_run_text.config(state=tk.NORMAL)
        self.plugins_run_text.delete("1.0", tk.END)
        if run_plugins:
            for p in run_plugins:
                pid = p.get("plugin_id", "").upper()
                status = p.get("status", "completed")
                signals = p.get("signal_count", 0)
                comps = p.get("competitor_count", 0)
                
                tag = "active"
                if status == "skipped":
                    tag = "skipped"
                elif status in ("failed", "error"):
                    tag = "error"

                self.plugins_run_text.insert(tk.END, f"• {pid} [{status.upper()}]\n", tag)
                self.plugins_run_text.insert(tk.END, f"  Signals extracted: {signals} | Competitors evaluated: {comps}\n")
        else:
            self.plugins_run_text.insert(tk.END, "No execution data returned.")
        self.plugins_run_text.config(state=tk.DISABLED)

        # Populate Raw Json Textbox
        self.raw_text.config(state=tk.NORMAL)
        self.raw_text.delete("1.0", tk.END)
        self.raw_text.insert("1.0", json.dumps(result, indent=2))
        self.raw_text.config(state=tk.DISABLED)

        # Refresh system plugins list in the left panel to update statuses
        self.load_plugins_status()

    def render_card_widget(self, val_label, grade_label, exp_label, card_data):
        score = card_data.get("score")
        if score is None:
            score = 0
        grade = card_data.get("grade", "Unknown")
        explanation = card_data.get("short_explanation", "No explanation.")
        factors = card_data.get("factors", [])


        val_label.config(text=str(score))
        grade_label.config(text=grade)
        
        # Color grade labels nicely
        grade_color = "#14b8a6"
        if score >= 90:
            grade_color = "#10b981"
        elif score >= 75:
            grade_color = "#14b8a6"
        elif score >= 60:
            grade_color = "#818cf8"
        elif score >= 40:
            grade_color = "#f59e0b"
        else:
            grade_color = "#ef4444"
        grade_label.config(foreground=grade_color)

        # Explanation + Factors bullets
        summary_text = explanation
        if factors:
            bullets = "\n".join([f"• {f}" for f in factors])
            summary_text += f"\n\n{bullets}"
        exp_label.config(text=summary_text)

    def display_analysis_error(self, error_msg, trace=None):
        self.status_indicator.config(foreground="#ef4444")
        self.status_text.config(text="Analysis Failed", foreground="#ef4444")
        self.analyze_btn.config(state=tk.NORMAL)
        self.clear_btn.config(state=tk.NORMAL)
        self.refresh_plugins_btn.config(state=tk.NORMAL)

        # Clear results panel
        self.current_export_path = None
        self.export_path_label.config(text="No export generated.")
        self.open_export_btn.config(state=tk.DISABLED)
        self.copy_path_btn.config(state=tk.DISABLED)
        self.hide_results_widgets()

        # Display placeholder with error
        err_display = f"\n\n\nError executing Cue analysis:\n{error_msg}"
        if trace:
            err_display += f"\n\nTechnical stack trace:\n{trace}"
        
        self.placeholder_label.config(text=err_display, foreground="#ef4444")
        self.placeholder_label.pack(pady=40, anchor="center")

        messagebox.showerror("Analysis Error", f"Cue analysis failed:\n{error_msg}")

    def on_clear_click(self):
        # Reset entries
        self.topic_entry.delete(0, tk.END)
        self.topic_entry.insert(0, "Michigan redistricting")
        self.platform_combo.set("podcast")
        self.tenant_entry.delete(0, tk.END)
        self.tenant_entry.insert(0, "local-test-tenant")
        self.user_entry.delete(0, tk.END)
        self.user_entry.insert(0, "local-test-user")
        self.workspace_entry.delete(0, tk.END)
        self.workspace_entry.insert(0, "local-test-workspace")
        self.debug_var.set(False)

        # Reset Results panel
        self.current_export_path = None
        self.export_path_label.config(text="No active run")
        self.open_export_btn.config(state=tk.DISABLED)
        self.copy_path_btn.config(state=tk.DISABLED)
        self.results_title.config(text="INTELLIGENCE REPORT")

        # Hide UI widgets & show clean placeholder
        self.hide_results_widgets()
        self.placeholder_label.config(text="\n\n\nNo report loaded. Configure inputs and click 'Run Cue Analysis'.", foreground="#94a3b8")
        self.placeholder_label.pack(pady=40, anchor="center")

        # System Status
        self.status_indicator.config(foreground="#94a3b8")
        self.status_text.config(text="System Ready", foreground="#f3f4f6")

        # Reload plugins
        self.load_plugins_status()

    def on_open_folder_click(self):
        if not self.current_export_path:
            return
        path = Path(self.current_export_path)
        # Convert path to absolute
        abs_path = path.resolve() if path.is_absolute() else (ROOT / path).resolve()
        
        if not abs_path.exists():
            messagebox.showerror("Error", f"Export file not found at: {abs_path}")
            return

        try:
            # Under Windows, open explorer and select the file
            import subprocess
            subprocess.run(["explorer", "/select,", os.path.normpath(str(abs_path))])
        except Exception as e:
            # Fallback
            try:
                os.startfile(abs_path.parent)
            except Exception as e2:
                messagebox.showerror("Error", f"Could not open folder:\n{e2}")

    def on_copy_path_click(self):
        if not self.current_export_path:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(str(self.current_export_path))
        messagebox.showinfo("Clipboard", "Export path copied to clipboard!")

    def toggle_raw_json(self):
        if self.show_raw_var.get():
            self.raw_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        else:
            self.raw_text.pack_forget()

    def hide_results_widgets(self):
        self.cards_frame.pack_forget()
        self.details_frame.pack_forget()
        self.gaps_frame.pack_forget()
        self.plugins_run_frame.pack_forget()
        self.raw_frame.pack_forget()

    def show_results_widgets(self):
        self.placeholder_label.pack_forget()
        self.cards_frame.pack(fill=tk.X, pady=(0, 20))
        self.details_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        self.gaps_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        self.plugins_run_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        self.raw_frame.pack(fill=tk.X)


# Helper utility functions
def last_status_is_active(status):
    return status in ("success", "active", "completed", "N/A")


def find_card_by_label(cards, label):
    for c in cards:
        if c.get("label") == label:
            return c
    return None


def main():
    root = tk.Tk()
    app = CueDesktopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

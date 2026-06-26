from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

# Add repository root to system path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.cue_desktop_app import CueDesktopApp


def test_desktop_app_functionality():
    """Verify default properties and safe 'None' last_run_status fallback on a single Tk instance."""
    root = tk.Tk()
    root.withdraw()

    # 1. Instantiate and check defaults
    app = CueDesktopApp(root)
    assert app.topic_entry.get() == "Michigan redistricting"
    assert app.platform_combo.get() == "podcast"
    assert app.tenant_entry.get() == "local-test-tenant"
    assert app.user_entry.get() == "local-test-user"
    assert app.workspace_entry.get() == "local-test-workspace"
    assert app.debug_var.get() is False

    assert app.analyze_btn is not None
    assert app.clear_btn is not None
    assert app.opp_val["text"] == "--"

    # 2. Test display_plugins_status with None last_run_status
    plugins = [
        {
            "plugin_id": "dummy_plugin",
            "plugin_name": "Dummy Plugin",
            "enabled": True,
            "configured": True,
            "last_run_status": None,
            "message": "Status is None",
            "missing_environment_variables": []
        }
    ]

    # This call should not raise an AttributeError
    app.display_plugins_status(plugins)

    # Confirm it renders 'NOT RUN' and plugin name properly
    text_content = app.plugins_status_text.get("1.0", tk.END)
    assert "NOT RUN" in text_content
    assert "Dummy Plugin" in text_content

    # Clean up
    root.update()
    root.destroy()

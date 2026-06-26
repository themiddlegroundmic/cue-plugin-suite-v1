# Cue Creator Intelligence Cockpit (Desktop Test App)

This is a local, high-fidelity Tkinter desktop test application for Cue. It provides a simple desktop GUI cockpit for non-developers to run intelligence reports, experiment with topics or RSS feeds, configure context parameters, and examine raw output.

> [!NOTE]
> This application is intended as a developer and local testing cockpit, not the final Volma production interface.

---

## Prerequisites & Installation

To run the application from source, you need Python 3 installed. No extra dependencies are required since standard `tkinter` is part of Python.

Install the project's dependencies:
```powershell
python -m pip install -r requirements.txt
```

---

## Running from Source

You can run the desktop application directly from the command line using:

```powershell
python scripts/cue_desktop_app.py
```

---

## Packaging into a Standalone Windows Executable (.exe)

You can package the application into a single executable that can be run on Windows machines without requiring a Python installation.

1. **Install PyInstaller**:
   ```powershell
   pip install pyinstaller
   ```

2. **Build the Executable**:
   Run the following command from the project root (`Cue_Plugin_Suite`):
   ```powershell
   pyinstaller --onefile --windowed --name="CueCockpit" scripts/cue_desktop_app.py
   ```
   
   - `--onefile`: Bundles everything into a single `.exe`.
   - `--windowed`: Hides the console window when the GUI starts.

3. **Where the `.exe` will appear**:
   After compilation completes, you will find the standalone executable inside the `dist/` directory:
   ```text
   Cue_Plugin_Suite/dist/CueCockpit.exe
   ```
   *Note: PyInstaller build folders (`build/`, `dist/`, and `.spec` files) are configured in `.gitignore` so they are not committed.*

---

## Using the Application

### 1. Parameters Setup
- **Topic or RSS Feed URL**: Enter a keyword topic (e.g., "Michigan redistricting") or a podcast/show RSS URL (starting with `http://` or `https://`).
- **Target Platform**: Select the platform matching your target output (e.g., `podcast`, `youtube`).
- **Tenant ID / User ID / Workspace ID**: Used to test tenant isolation and scoping.
- **Enable Debug Diagnostics**: Check this box to display technical diagnostics and stack traces directly in the UI in case of errors.

### 2. Analysis & Visualizations
- Click **Run Cue Analysis** to start the analysis. The processing is executed asynchronously in a background thread so the GUI will not freeze.
- On completion, the dashboard will display:
  - **Scores Card**: Opportunity, Platform Readiness, and Confidence Scores with calculated grades.
  - **Score Explanations**: Detailed factors and descriptions for each score.
  - **Key Recommendations & Insights**: Actions based on findings.
  - **Identified Content Gaps**: Topic, supporting signals, and recommended angle.
  - **Creator Generated Output**: Title ideas, description hook, and optimized tags.
  - **Plugin Execution Details**: Breakdowns of run status and signals.
  - **Raw JSON Response**: Toggle the raw response checkbox to display the exact JSON structure.

### 3. Open Export Location
- Clicking **Open Folder** in the top export area opens Windows Explorer with the generated export JSON file highlighted.
- Clicking **Copy Path** copies the file path directly to your clipboard.

### 4. YouTube API Key Note
- The YouTube plugin requires the `YOUTUBE_API_KEY` environment variable. If this is not set, the YouTube plugin skips safely and documents this on the dashboard status.

# IngeTrazo Twinmotion LiveSync Extension

<p align="left">
  <a href="https://github.com/sponsors/SPACIO-TECHTONICS">
    <img src="https://img.shields.io/badge/Sponsor-%E2%9D%A4-ea4aaa?style=for-the-badge&logo=githubsponsors" alt="Sponsor on GitHub" />
  </a>
  <a href="LICENSE">
    <img src="https://img.shields.io/badge/License-GPL--3.0-10b981?style=for-the-badge" alt="License: GPL-3.0" />
  </a>
</p>

This extension provides real-time synchronization between **IngeTrazo** (open-source 3D CAD/BIM modeler) and **Twinmotion** using the Epic Games Datasmith DirectLink protocol.

---

## License

This project is licensed under the **GNU General Public License v3.0 or later (GPL-3.0-or-later)**; see [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).
Epic Games, Unreal, and Twinmotion runtime components remain subject to separate Epic Games terms.

---

## Installation & Setup

You can set up the extension using the self-healing in-app mode, the desktop GUI installer, or the command line.

### Option 1: Zero-Config In-App Self-Healing (Easiest)

You do not need to install Rhino or pre-install Epic Datasmith DLLs.
1. Copy or install the extension folder to `%APPDATA%\ingetrazo\plugins\igz_tm_livesync`.
2. Open IngeTrazo and activate **Extensions** -> **Twinmotion LiveSync**.
3. Click **Connect** (or **⚡ Sync to Twinmotion**).
4. The extension automatically detects missing runtime components. It downloads the official Epic Datasmith installer online, extracts the required DLLs, and compiles the C# worker.
5. The sidebar **Activity Log** and status banner show live progress (download percentage and compilation status).

### Option 2: Desktop GUI Installer

Run `python setup_app.py` or double-click `setup_app.pyw`.
The application checks your environment automatically:
- Checks Windows x64 and .NET Framework C# compiler (`csc.exe`).
- Searches for the official Epic Datasmith runtime.
- If the runtime is missing, it searches online and downloads the official Epic installer.
- Verifies the installer SHA256 checksum and extracts the required runtime libraries.
- Compiles the DirectLink worker and installs the extension to IngeTrazo with one click.

### Option 3: Command Line Setup

Run the setup helper script:

```powershell
python setup_local.py
```

The script auto-detects existing Datasmith installations or downloads missing runtime libraries automatically.
You can also supply an existing vendor folder:

```powershell
python setup_local.py --vendor-dir 'C:\DatasmithRuntime'
```

---

## Features

### 1. Sequential Option Management
- Saves and updates `TM Option N` layer visibility presets.
- Sorts options numerically (`TM Option 2` displays before `TM Option 10`).
- Generates the next sequential option name automatically without manual text input.

### 2. State Preservation (`try...finally`)
- Saves the working camera projection before export.
- Caches active working layer visibility states before export.
- Temporarily unhides hidden objects on active export layers during synchronization.
- Restores all working layers, camera projections, and hidden objects after export.

### 3. Real-Time DCC Camera Sync
- Streams active IngeTrazo camera perspectives to Twinmotion at ~25 to 28 updates per second.
- The Twinmotion viewport follows the IngeTrazo modeler view in real time (requires Twinmotion 2025.2 or newer).

### 4. Custom SVG Toolbar & Side Panel
- Provides a compact toolbar with custom SVG actions:
  - **Connect**: Starts the background DirectLink worker.
  - **Sync Now**: Pushes the current model snapshot to Twinmotion.
  - **Option +**: Creates the next sequential `TM Option N` preset.
  - **Camera**: Toggles real-time DCC camera tracking.
  - **Disconnect**: Stops the worker and closes network sockets.
- Provides a dockable PySide6 side panel in the IngeTrazo side tray.
- Uses neutral dark slate, emerald green, and amber colors without blue colors or gradients.

---

## Architecture & Design Decisions

The extension uses a three-tier architecture:

```text
[ IngeTrazo (Python / PySide6) ]
           │  (Local TCP Port 19850 - JSON IPC)
           ▼
[ DatasmithWorker.exe (C# / .NET) ]
           │  (Native P/Invoke)
           ▼
[ DatasmithFacadeCSharp.dll + tbbmalloc.dll ]
           │  (Unreal MessageBus / UDP Port 6666)
           ▼
[ Twinmotion (Direct Link Receiver) ]
```

### Design Decisions:
1. **Out-of-Process Background Worker (`DatasmithWorker.exe`)**:
   - Native C++ Datasmith operations run in an independent process via `subprocess.Popen`.
   - Prevents memory violations or blocking operations from freezing the IngeTrazo Qt user interface.
2. **Native P/Invoke Interop**:
   - The worker directly calls `DatasmithFacadeCSharp.dll` without external Rhino dependencies.
   - Operates completely standalone without requiring Rhino or Unreal Editor to run.
3. **Unreal MessageBus Messaging**:
   - `FDatasmithExporterManager::Initialize` is called with `bEnableMessaging = true`.
   - Broadcasts UDP beacons on port 6666 so Twinmotion immediately discovers the source.
4. **Coordinate Scaling**:
   - Automatically converts IngeTrazo meters to Twinmotion centimeters ($\times 100$ scale factor).

---

## Repository Files

```text
f:\igz-tm-livesync\
├── .env                  # Environment settings (ports, names, unit scale)
├── .env.example          # Configuration template
├── .gitignore            # Git exclusion rules
├── LICENSE               # GNU General Public License v3.0 or later (GPL-3.0-or-later)
├── NOTICE.md             # Third-party notices and attribution
├── plugin.json           # Extension manifest for IngeTrazo
├── __init__.py           # Package entry point
├── igz_tm_sync.py        # Core extension, tool registration, and side panel
├── directlink_bridge.py  # Worker process manager and TCP IPC client
├── mesh_exporter.py      # Geometry extraction, triangulation, and materials
├── runtime_downloader.py # Automated Datasmith download and checksum verification
├── setup_app.py          # Standalone Desktop GUI installer (Dark Emerald theme)
├── setup_app.pyw         # Windowless double-clickable installer entry point
├── DatasmithWorker.cs    # C# background worker source (Datasmith P/Invoke)
├── DatasmithWorker.exe   # Compiled 64-bit worker executable
├── setup_local.py        # Build, download, and deployment helper
├── test_extension.py     # Extension test suite
├── test_runtime_installer.py # Runtime installer test suite
├── icons/                # Custom SVG toolbar icons (emerald, amber, neutral)
└── README.md             # Documentation
```

---

## Requirements

- **Operating System**: Windows 10 / 11 (64-bit).
- **IngeTrazo**: Installed on your system.
- **Twinmotion**: Version 2025.2 or newer (tested with Twinmotion 2026.1).
- **Compiler**: Windows .NET Framework 64-bit C# compiler (included with Windows at `C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe`).
- **Datasmith Runtime**: Automatically downloaded and verified online by the extension on first run, or auto-detected if already on your system. No Rhino installation is required.

---

## How to Use

1. **Start Twinmotion**:
   - Launch Twinmotion and create a new project.
2. **Start IngeTrazo**:
   - Launch IngeTrazo and open your 3D project.
3. **Open the LiveSync Tool**:
   - Open **Extensions** -> **Twinmotion LiveSync** (or press `Ctrl+Shift+T`).
   - The toolbar and the **Twinmotion LiveSync** side panel will display.
4. **Manage Options**:
   - Click **`+ Create Next Option`** to capture current layer visibility as `TM Option N`.
   - Click **`Update from Viewport`** to save changes to the current option.
5. **Connect & Synchronize**:
   - Click the **Connect** icon (or **⚡ Sync to Twinmotion** in the side panel).
   - IngeTrazo launches the background worker and registers the DirectLink source.
6. **Import in Twinmotion**:
   - In Twinmotion, open **Import** -> **DIRECT LINK**.
   - Select **IngeTrazo LiveSync** in the **Direct Link settings source** dropdown.
   - Click **Import**.
7. **Enable Real-Time Camera Sync**:
   - Click the **Camera** icon in IngeTrazo (or check **🎥 DCC Camera Sync** in the side panel).
   - In Twinmotion viewport settings, enable **DCC Camera Sync** -> **IngeTrazo Active View**.
   - Moving your camera in IngeTrazo immediately updates the Twinmotion camera view.

---

## Configuration (`.env`)

Configuration settings are stored in [.env](file:///f:/igz-tm-livesync/.env):

```ini
# Network settings
DIRECTLINK_HOST=127.0.0.1
DIRECTLINK_PORT=6666

# Source and stream labels displayed in Twinmotion
DIRECTLINK_SOURCE_NAME=IngeTrazo
DIRECTLINK_STREAM_NAME=IngeTrazo LiveSync

# Coordinate unit scaling (1 meter = 100 centimeters)
DIRECTLINK_UNIT_SCALE=100.0
```

> [!NOTE]
> Do not store sensitive passwords or credentials in `.env`.

---

## Testing & Verification

Run the test suite to verify the installer, runtime downloader, option sorting, state restoration, triangulation, and snapshot generation:

```powershell
python -m unittest test_runtime_installer.py test_extension.py
```

---

## Attribution & Inspiration

This project is inspired by open-source community work:

- **[hamzah1985/ingetrazo-twinmotion-sync](https://github.com/hamzah1985/ingetrazo-twinmotion-sync)** by Hamzah:
  Provided the reference architecture for unmanaged Datasmith SDK interop, background C# worker design, and IngeTrazo Qt plugin integration.

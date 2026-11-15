"""
IngeTrazo Twinmotion LiveSync - Automated Setup and Runtime Downloader
Provides a desktop interface to verify system requirements, download official
Epic Datasmith runtime if needed, compile the C# worker, and install the extension.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parent

# Color Palette: Modern Dark Emerald (Strictly NO Blue)
BG_MAIN = "#121214"
BG_CARD = "#1c1c20"
BG_CARD_INNER = "#25252b"
BORDER_COLOR = "#2e2e36"
TEXT_PRIMARY = "#f4f4f6"
TEXT_SECONDARY = "#a1a1aa"
TEXT_MUTED = "#71717a"
ACCENT_EMERALD = "#10b981"
ACCENT_EMERALD_HOVER = "#059669"
ACCENT_AMBER = "#f59e0b"
ACCENT_RED = "#ef4444"
LOG_BG = "#0d0d0f"
LOG_FG = "#34d399"

MSI_URL = "https://unrealstudio.epicgames.com/UnrealDatasmithRhinoExporter_5_8_400.msi"
MSI_SHA256 = "7f0e3039e9c8a772b20654342854d497c16799a92077ba2a9df0e9076f1b1927"

RUNTIME_HASHES = {
    'DatasmithFacadeCSharp.dll': 'eb3e4881629244bbc3a5cb1062aa579d79f68ebb682b5140a274c7c0d1d6fc08',
    'DatasmithRhino6.rhp': '77e2073dc7bd792896f976562f97f125dd1289231338b20ef5bd8d2b6795cd1d',
    'tbbmalloc.dll': '87abcd8f7e31003ab049962a97eb645310be1ccab7ba148c46b2cde5262027bf',
}


class SetupApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("IngeTrazo Twinmotion LiveSync - Setup")
        self.root.geometry("720x760")
        self.root.minsize(680, 700)
        self.root.configure(bg=BG_MAIN)

        self.vendor_dir = None
        self.compiler_path = None
        self.is_installing = False

        self._init_styles()
        self._build_ui()
        self._check_prerequisites()

    def _init_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Emerald.Horizontal.TProgressbar",
                        background=ACCENT_EMERALD,
                        troughcolor=BG_CARD_INNER,
                        bordercolor=BORDER_COLOR,
                        lightcolor=ACCENT_EMERALD,
                        darkcolor=ACCENT_EMERALD)

    def _build_ui(self):
        # Header
        header = tk.Frame(self.root, bg=BG_MAIN, padx=24, pady=16)
        header.pack(fill=tk.X)

        title_row = tk.Frame(header, bg=BG_MAIN)
        title_row.pack(fill=tk.X)

        title = tk.Label(
            title_row,
            text="IngeTrazo Twinmotion LiveSync",
            font=("Segoe UI", 18, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_MAIN
        )
        title.pack(side=tk.LEFT, anchor="w")

        btn_sponsor = tk.Button(
            title_row,
            text="💖 Sponsor",
            font=("Segoe UI", 9, "bold"),
            bg=BG_CARD,
            fg="#fb7185",
            activebackground=BG_CARD_INNER,
            activeforeground="#f43f5e",
            bd=1,
            relief=tk.SOLID,
            padx=10,
            pady=3,
            cursor="hand2",
            command=lambda: webbrowser.open("https://github.com/sponsors/SPACIO-TECHTONICS")
        )
        btn_sponsor.pack(side=tk.RIGHT)

        subtitle = tk.Label(
            header,
            text="Automated installer and official Datasmith DirectLink runtime setup",
            font=("Segoe UI", 10),
            fg=TEXT_SECONDARY,
            bg=BG_MAIN
        )
        subtitle.pack(anchor="w", pady=(2, 0))

        # Status Cards Container
        cards_frame = tk.Frame(self.root, bg=BG_MAIN, padx=24)
        cards_frame.pack(fill=tk.X, pady=(0, 10))

        self.card_os = self._create_status_card(cards_frame, "Operating System", "Checking...")
        self.card_compiler = self._create_status_card(cards_frame, ".NET C# Compiler", "Checking...")
        self.card_runtime = self._create_status_card(cards_frame, "Datasmith Runtime", "Checking...")
        self.card_plugin = self._create_status_card(cards_frame, "Plugin Target", "Checking...")

        # Progress Section
        progress_frame = tk.Frame(self.root, bg=BG_CARD, bd=1, relief=tk.SOLID, padx=16, pady=14)
        progress_frame.pack(fill=tk.X, padx=24, pady=(6, 12))

        self.status_label = tk.Label(
            progress_frame,
            text="Ready to install or verify system.",
            font=("Segoe UI", 10, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD,
            anchor="w"
        )
        self.status_label.pack(fill=tk.X)

        self.substatus_label = tk.Label(
            progress_frame,
            text="Click 'Install & Setup' to start automatic configuration.",
            font=("Segoe UI", 9),
            fg=TEXT_SECONDARY,
            bg=BG_CARD,
            anchor="w"
        )
        self.substatus_label.pack(fill=tk.X, pady=(2, 8))

        self.progress_bar = ttk.Progressbar(
            progress_frame,
            orient="horizontal",
            length=100,
            mode="determinate",
            style="Emerald.Horizontal.TProgressbar"
        )
        self.progress_bar.pack(fill=tk.X)

        # Action Buttons
        btn_frame = tk.Frame(self.root, bg=BG_MAIN, padx=24)
        btn_frame.pack(fill=tk.X, pady=(0, 12))

        self.btn_install = tk.Button(
            btn_frame,
            text="Install & Setup",
            font=("Segoe UI", 11, "bold"),
            bg=ACCENT_EMERALD,
            fg="#000000",
            activebackground=ACCENT_EMERALD_HOVER,
            activeforeground="#ffffff",
            bd=0,
            padx=20,
            pady=10,
            cursor="hand2",
            command=self._start_installation
        )
        self.btn_install.pack(side=tk.LEFT, padx=(0, 10))

        self.btn_verify = tk.Button(
            btn_frame,
            text="Check Environment Only",
            font=("Segoe UI", 10),
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            activebackground=BG_CARD_INNER,
            activeforeground=TEXT_PRIMARY,
            bd=1,
            padx=16,
            pady=9,
            cursor="hand2",
            command=self._check_prerequisites
        )
        self.btn_verify.pack(side=tk.LEFT)

        # Activity Log Container
        log_container = tk.Frame(self.root, bg=BG_MAIN, padx=24)
        log_container.pack(fill=tk.BOTH, expand=True, pady=(0, 16))

        log_header = tk.Label(
            log_container,
            text="Activity Log",
            font=("Segoe UI", 10, "bold"),
            fg=TEXT_SECONDARY,
            bg=BG_MAIN
        )
        log_header.pack(anchor="w", pady=(0, 4))

        self.log_text = tk.Text(
            log_container,
            bg=LOG_BG,
            fg=LOG_FG,
            insertbackground=TEXT_PRIMARY,
            font=("Consolas", 9),
            bd=1,
            relief=tk.SOLID,
            wrap=tk.WORD,
            padx=8,
            pady=8
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _create_status_card(self, parent, title_text, initial_value):
        frame = tk.Frame(parent, bg=BG_CARD, bd=1, relief=tk.SOLID, padx=12, pady=10)
        frame.pack(fill=tk.X, pady=3)

        title = tk.Label(frame, text=title_text, font=("Segoe UI", 9, "bold"),
                         fg=TEXT_SECONDARY, bg=BG_CARD)
        title.pack(side=tk.LEFT)

        val_label = tk.Label(frame, text=initial_value, font=("Segoe UI", 9),
                             fg=TEXT_PRIMARY, bg=BG_CARD)
        val_label.pack(side=tk.RIGHT)
        return val_label

    def log(self, message: str):
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def _update_progress(self, message: str, percent: float, submessage: str = ""):
        self.status_label.config(text=message)
        if submessage:
            self.substatus_label.config(text=submessage)
        self.progress_bar["value"] = percent * 100

    def _check_prerequisites(self):
        self.log("Verifying system configuration...")

        # 1. OS Architecture
        if os.name == 'nt':
            self.card_os.config(text="Windows x64 (Compatible)", fg=ACCENT_EMERALD)
        else:
            self.card_os.config(text="Unsupported OS (Windows x64 required)", fg=ACCENT_RED)

        # 2. .NET C# Compiler
        compiler = Path(os.environ.get('WINDIR', 'C:\\Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
        if compiler.is_file():
            self.compiler_path = compiler
            self.card_compiler.config(text="Ready (.NET Framework 4.0 x64)", fg=ACCENT_EMERALD)
            self.log(f"Compiler found: {compiler}")
        else:
            self.compiler_path = None
            self.card_compiler.config(text="Missing (.NET Framework required)", fg=ACCENT_RED)
            self.log("ERROR: .NET Framework x64 C# compiler not found.")

        # 3. Datasmith Runtime
        self.vendor_dir = self._find_runtime()
        if self.vendor_dir:
            self.card_runtime.config(text=f"Detected ({self.vendor_dir.name})", fg=ACCENT_EMERALD)
            self.log(f"Datasmith runtime detected at: {self.vendor_dir}")
        else:
            self.card_runtime.config(text="Missing (Will auto-download from Epic)", fg=ACCENT_AMBER)
            self.log("Datasmith runtime not found. Automated download is ready.")

        # 4. Plugin Destination
        appdata = Path(os.environ.get('APPDATA', ''))
        plugin_dir = appdata / 'ingetrazo/plugins/igz_tm_livesync'
        if plugin_dir.exists():
            self.card_plugin.config(text="Installed (Ready for update)", fg=ACCENT_EMERALD)
        else:
            self.card_plugin.config(text="Not installed", fg=TEXT_SECONDARY)

    def _find_runtime(self):
        candidates = [
            Path(os.environ.get('LOCALAPPDATA', '')) / 'IngeTrazo' / 'twinmotion_sync' / 'vendor',
            Path(r"C:\DatasmithRuntime"),
            Path(r"C:\ProgramData\McNeel\Rhinoceros\7.0\Plug-ins\Datasmith Rhino Exporter (d1fdc795-b334-4933-b680-088119cdc6bb)"),
            Path(r"C:\ProgramData\McNeel\Rhinoceros\6.0\Plug-ins\Datasmith Rhino Exporter (d1fdc795-b334-4933-b680-088119cdc6bb)"),
            Path(r"C:\ProgramData\McNeel\Rhinoceros\8.0\Plug-ins\Datasmith Rhino Exporter (d1fdc795-b334-4933-b680-088119cdc6bb)"),
        ]
        for c in candidates:
            if c.is_dir() and self._verify_runtime_dir(c):
                return c.resolve()
        return None

    def _verify_runtime_dir(self, directory: Path) -> bool:
        for name, expected_hash in RUNTIME_HASHES.items():
            f = directory / name
            if not f.is_file():
                return False
            try:
                if hashlib.sha256(f.read_bytes()).hexdigest() != expected_hash:
                    return False
            except Exception:
                return False
        return True

    def _start_installation(self):
        if self.is_installing:
            return
        if not self.compiler_path:
            messagebox.showerror("Missing Requirement", "Windows .NET Framework x64 compiler is required.")
            return

        self.is_installing = True
        self.btn_install.config(state=tk.DISABLED, bg=BG_CARD_INNER, fg=TEXT_MUTED)
        self.btn_verify.config(state=tk.DISABLED)

        thread = threading.Thread(target=self._run_install_worker, daemon=True)
        thread.start()

    def _run_install_worker(self):
        try:
            # Step 1: Ensure Runtime
            if not self.vendor_dir or not self._verify_runtime_dir(self.vendor_dir):
                self._post_update("Searching and downloading Datasmith runtime...", 0.1, "Connecting to Epic Games...")
                self.vendor_dir = self._download_and_extract_runtime()

            # Step 2: Compile DatasmithWorker.exe
            self._post_update("Compiling Datasmith Worker...", 0.75, "Running C# compiler...")
            self._post_log("Compiling C# worker with .NET Framework compiler...")
            worker_cs = ROOT / "DatasmithWorker.cs"
            worker_out = ROOT / "DatasmithWorker.exe"

            cmd = [
                str(self.compiler_path),
                "/nologo",
                "/target:exe",
                "/platform:x64",
                "/optimize+",
                f"/out:{worker_out}",
                str(worker_cs)
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                raise RuntimeError(f"C# compilation failed: {res.stderr}")
            self._post_log("Worker compiled successfully.")

            # Step 3: Install Plugin Files
            self._post_update("Installing IngeTrazo LiveSync extension...", 0.85, "Deploying plugin files...")
            self._post_log("Deploying plugin to IngeTrazo plugins directory...")
            import setup_local
            setup_local.install_plugin(self.vendor_dir)

            target_plugin_dir = Path(os.environ.get('APPDATA', '')) / 'ingetrazo/plugins/igz_tm_livesync'
            self._post_log(f"Extension installed to: {target_plugin_dir}")

            # Step 4: Finished
            self._post_update("Installation Complete!", 1.0, "Twinmotion LiveSync is ready to use.")
            self._post_log("Installation finished successfully!")

            self.root.after(0, lambda: self._show_success_dialog(str(target_plugin_dir)))

        except Exception as e:
            self._post_update("Installation Failed", 0.0, str(e))
            self._post_log(f"ERROR: {e}")
            self.root.after(0, lambda: messagebox.showerror("Installation Error", str(e)))

        finally:
            self.is_installing = False
            self.root.after(0, self._restore_buttons)
            self.root.after(0, self._check_prerequisites)

    def _download_and_extract_runtime(self) -> Path:
        target_dir = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'IngeTrazo' / 'twinmotion_sync' / 'vendor'
        target_dir.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            msi_path = temp_path / "UnrealDatasmithRhinoExporter.msi"
            extract_dir = temp_path / "extracted"
            extract_dir.mkdir(exist_ok=True)

            self._post_log(f"Downloading official installer from: {MSI_URL}")

            def report_hook(block_num, block_size, total_size):
                if total_size > 0:
                    downloaded = block_num * block_size
                    pct = min(0.65, 0.1 + (downloaded / total_size) * 0.55)
                    mb_down = downloaded / (1024 * 1024)
                    mb_total = total_size / (1024 * 1024)
                    self._post_update(
                        f"Downloading Datasmith Installer: {mb_down:.1f} / {mb_total:.1f} MB",
                        pct,
                        "Downloading official Epic installer..."
                    )

            urllib.request.urlretrieve(MSI_URL, str(msi_path), reporthook=report_hook)

            # Verify Checksum
            self._post_update("Verifying installer package...", 0.68, "Calculating SHA256...")
            self._post_log("Verifying installer checksum...")
            actual_hash = hashlib.sha256(msi_path.read_bytes()).hexdigest()
            if actual_hash != MSI_SHA256:
                raise ValueError("MSI checksum mismatch! Download may be corrupted.")
            self._post_log("Installer checksum verified.")

            # Extract via msiexec administrative mode
            self._post_update("Extracting runtime files...", 0.70, "Unpacking MSI without system changes...")
            self._post_log("Extracting runtime files via msiexec...")
            extract_cmd = ["msiexec.exe", "/a", str(msi_path), "/qn", f"TARGETDIR={extract_dir}"]
            ext_res = subprocess.run(extract_cmd, capture_output=True, text=True)
            if ext_res.returncode != 0:
                raise RuntimeError(f"MSI extraction failed: {ext_res.stderr}")

            # Locate and copy runtime files
            found = {}
            for p in extract_dir.rglob("*"):
                if p.is_file() and p.name in RUNTIME_HASHES:
                    found[p.name] = p

            for name, expected_hash in RUNTIME_HASHES.items():
                if name not in found:
                    raise FileNotFoundError(f"Missing extracted file: {name}")
                src = found[name]
                if hashlib.sha256(src.read_bytes()).hexdigest() != expected_hash:
                    raise ValueError(f"Extracted checksum mismatch for: {name}")
                shutil.copy2(src, target_dir / name)
                self._post_log(f"Installed runtime component: {name}")

        if not self._verify_runtime_dir(target_dir):
            raise RuntimeError("Verification failed for extracted runtime.")

        self._post_log(f"Datasmith runtime successfully placed at: {target_dir}")
        return target_dir

    def _post_update(self, message: str, percent: float, submessage: str = ""):
        self.root.after(0, lambda: self._update_progress(message, percent, submessage))

    def _post_log(self, message: str):
        self.root.after(0, lambda: self.log(message))

    def _restore_buttons(self):
        self.btn_install.config(state=tk.NORMAL, bg=ACCENT_EMERALD, fg="#000000")
        self.btn_verify.config(state=tk.NORMAL)

    def _show_success_dialog(self, plugin_path: str):
        msg = (
            "IngeTrazo Twinmotion LiveSync installed successfully!\n\n"
            "Next Steps:\n"
            "1. Start IngeTrazo and open your model.\n"
            "2. Open Extensions -> Twinmotion LiveSync (or press Ctrl+Shift+T).\n"
            "3. Click Connect, then open Twinmotion and select Import -> DirectLink."
        )
        messagebox.showinfo("Setup Completed", msg)


def main():
    root = tk.Tk()
    app = SetupApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()

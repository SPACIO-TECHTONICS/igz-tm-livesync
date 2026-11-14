"""
Local Build and Setup Helper for IngeTrazo Twinmotion LiveSync.
Modeled after the hamzah1985/ingetrazo-twinmotion-sync setup workflow.

Functions:
- Locates Datasmith runtime binaries (DatasmithFacadeCSharp.dll, tbbmalloc.dll).
- Compiles DatasmithWorker.cs with the Windows .NET Framework 64-bit compiler.
- Copies the extension files into the IngeTrazo user plugins folder.
"""

import os
import sys
import shutil
import subprocess
import argparse

CSC_PATH = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
DEFAULT_INGETRAZO_PLUGINS = os.path.expandvars(r"%APPDATA%\ingetrazo\plugins\igz_tm_livesync")


def find_datasmith_runtime(vendor_dir=None):
    """Searches for DatasmithFacadeCSharp.dll in vendor directory or common paths."""
    candidates = []
    if vendor_dir:
        candidates.append(vendor_dir)

    # Search common Rhino and Epic Games installation locations
    candidates.extend([
        r"C:\ProgramData\McNeel\Rhinoceros\7.0\Plug-ins\Datasmith Rhino Exporter (d1fdc795-b334-4933-b680-088119cdc6bb)",
        r"C:\ProgramData\McNeel\Rhinoceros\7.0\Plug-ins",
        os.path.expandvars(r"%APPDATA%\McNeel\Rhinoceros\7.0\Plug-ins"),
        r"C:\Program Files\Epic Games\Twinmotion",
        r"C:\Program Files\Epic Games\DatasmithCADPlugins",
        r"C:\DatasmithRuntime"
    ])

    for base in candidates:
        if not os.path.isdir(base):
            continue
        for root, _, files in os.walk(base):
            if "DatasmithFacadeCSharp.dll" in files:
                return root
    return None


def compile_worker(source_file, output_exe, vendor_dir=None):
    """Compiles the C# Datasmith worker using csc.exe."""
    if not os.path.isfile(CSC_PATH):
        print(f"[Error] C# compiler not found at: {CSC_PATH}")
        return False

    # Stop any running DatasmithWorker before compiling
    try:
        subprocess.run(["taskkill", "/F", "/IM", "DatasmithWorker.exe"], capture_output=True)
    except Exception:
        pass

    runtime_dir = find_datasmith_runtime(vendor_dir)
    if runtime_dir:
        print(f"[Setup] Found Datasmith runtime at: {runtime_dir}")

    cmd = [
        CSC_PATH,
        "/target:exe",
        "/platform:x64",
        "/optimize+",
        f"/out:{output_exe}",
        source_file
    ]

    print(f"[Setup] Compiling worker: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print("[Setup] Worker compiled successfully.")
        return True
    else:
        err_msg = result.stdout if result.stdout else result.stderr
        print(f"[Error] Compilation failed:\n{err_msg}")
        return False


def install_plugin(target_dir=DEFAULT_INGETRAZO_PLUGINS):
    """Copies all extension files into IngeTrazo plugins folder."""
    os.makedirs(target_dir, exist_ok=True)
    src_dir = os.path.dirname(os.path.abspath(__file__))

    # Stop any running DatasmithWorker process to release file lock
    try:
        subprocess.run(["taskkill", "/F", "/IM", "DatasmithWorker.exe"], capture_output=True)
        import time
        time.sleep(0.8)
    except Exception:
        pass

    files_to_copy = [
        "__init__.py",
        "plugin.json",
        "igz_tm_sync.py",
        "directlink_bridge.py",
        "mesh_exporter.py",
        ".env",
        "README.md"
    ]
    if os.path.isfile(os.path.join(src_dir, "DatasmithWorker.exe")):
        files_to_copy.append("DatasmithWorker.exe")

    for fname in files_to_copy:
        src = os.path.join(src_dir, fname)
        if os.path.isfile(src):
            dst = os.path.join(target_dir, fname)
            copied = False
            for attempt in range(3):
                try:
                    shutil.copy2(src, dst)
                    print(f"[Setup] Installed: {dst}")
                    copied = True
                    break
                except PermissionError:
                    subprocess.run(["taskkill", "/F", "/IM", "DatasmithWorker.exe"], capture_output=True)
                    import time
                    time.sleep(1.0)
            if not copied:
                print(f"[Setup] Warning: Could not overwrite {fname} (process still holding file).")

    # Copy icons directory
    icons_src = os.path.join(src_dir, "icons")
    icons_dst = os.path.join(target_dir, "icons")
    if os.path.isdir(icons_src):
        os.makedirs(icons_dst, exist_ok=True)
        for icon_file in os.listdir(icons_src):
            if icon_file.endswith(".svg"):
                shutil.copy2(os.path.join(icons_src, icon_file), os.path.join(icons_dst, icon_file))
                print(f"[Setup] Installed Icon: {icon_file}")

    # Ensure obsolete single-file launcher is removed if present
    plugins_parent = os.path.dirname(target_dir)
    forwarder_file = os.path.join(plugins_parent, "igz_tm_livesync_plugin.py")
    if os.path.isfile(forwarder_file):
        try:
            os.remove(forwarder_file)
            print(f"[Setup] Cleaned up obsolete launcher: {forwarder_file}")
        except Exception:
            pass

    print(f"\n[Setup] Successfully installed extension to: {target_dir}")


def main():
    parser = argparse.ArgumentParser(description="Build and setup IngeTrazo Twinmotion LiveSync extension.")
    parser.add_argument("--vendor-dir", help="Path to Epic Datasmith runtime files (DatasmithFacadeCSharp.dll)")
    parser.add_argument("--install-dir", default=DEFAULT_INGETRAZO_PLUGINS, help="IngeTrazo plugins folder")
    parser.add_argument("--build-only", action="store_true", help="Compile worker without installing")
    args = parser.parse_args()

    src_dir = os.path.dirname(os.path.abspath(__file__))
    source_cs = os.path.join(src_dir, "DatasmithWorker.cs")
    output_exe = os.path.join(src_dir, "DatasmithWorker.exe")

    compile_worker(source_cs, output_exe, args.vendor_dir)

    if not args.build_only:
        install_plugin(args.install_dir)


if __name__ == "__main__":
    main()

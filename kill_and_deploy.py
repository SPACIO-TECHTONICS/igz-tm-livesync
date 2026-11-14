"""
Kill DatasmithWorker processes by PID, deploy updated files, and verify
"""
import subprocess
import shutil
import time
import os

print("[1] Killing DatasmithWorker processes by PID...")
subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Process -Name DatasmithWorker -ErrorAction SilentlyContinue | Stop-Process -Force"], capture_output=True)
time.sleep(1.5)

# Verify no DatasmithWorker is running
check = subprocess.run(["tasklist", "/FI", "IMAGENAME eq DatasmithWorker.exe"], capture_output=True, text=True)
if "DatasmithWorker.exe" in check.stdout:
    print("Warning: Process still active, forcing taskkill...")
    subprocess.run(["taskkill", "/F", "/T", "/IM", "DatasmithWorker.exe"], capture_output=True)
    time.sleep(1.0)
else:
    print("All DatasmithWorker processes stopped.")

src_dir = r"F:\igz-tm-livesync"
csc_path = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
source_cs = os.path.join(src_dir, "DatasmithWorker.cs")
output_exe = os.path.join(src_dir, "DatasmithWorker.exe")
deploy_dir = os.path.expandvars(r"%APPDATA%\ingetrazo\plugins\igz_tm_livesync")
deployed_exe = os.path.join(deploy_dir, "DatasmithWorker.exe")

print("[2] Compiling latest DatasmithWorker.cs...")
cmd = [
    csc_path,
    "/target:exe",
    "/platform:x64",
    "/optimize+",
    f"/out:{output_exe}",
    source_cs
]
res = subprocess.run(cmd, capture_output=True, text=True)
if res.returncode != 0:
    print(f"Compilation error:\n{res.stdout}\n{res.stderr}")
    exit(1)
print("Compiled DatasmithWorker.exe successfully.")

print("[3] Deploying new DatasmithWorker.exe...")
shutil.copy2(output_exe, deployed_exe)
print(f"Installed: {deployed_exe}")

print("[4] Deploying updated python connector files...")
for fn in ["directlink_bridge.py", "mesh_exporter.py", "igz_tm_sync.py", "__init__.py", "plugin.json"]:
    src = os.path.join(src_dir, fn)
    dst = os.path.join(deploy_dir, fn)
    shutil.copy2(src, dst)
    print(f"Installed: {dst}")

print("\n[SUCCESS] All files deployed successfully!")

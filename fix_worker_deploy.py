"""
Force stop running workers, recompile, deploy, and verify socket responsiveness on 19850
"""
import subprocess
import shutil
import time
import socket
import os

print("[1] Terminating all running DatasmithWorker processes...")
subprocess.run(["taskkill", "/F", "/IM", "DatasmithWorker.exe"], capture_output=True)
time.sleep(1.0)

src_dir = r"F:\igz-tm-livesync"
csc_path = r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
source_cs = os.path.join(src_dir, "DatasmithWorker.cs")
output_exe = os.path.join(src_dir, "DatasmithWorker.exe")
deploy_dir = os.path.expandvars(r"%APPDATA%\ingetrazo\plugins\igz_tm_livesync")
deployed_exe = os.path.join(deploy_dir, "DatasmithWorker.exe")

print("[2] Compiling DatasmithWorker.cs...")
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
print("Worker compiled successfully.")

print("[3] Deploying to IngeTrazo plugin folder...")
shutil.copy2(output_exe, deployed_exe)
print(f"Installed: {deployed_exe}")

# Also copy directlink_bridge.py, mesh_exporter.py, igz_tm_sync.py
for fn in ["directlink_bridge.py", "mesh_exporter.py", "igz_tm_sync.py", "__init__.py", "plugin.json"]:
    src = os.path.join(src_dir, fn)
    dst = os.path.join(deploy_dir, fn)
    shutil.copy2(src, dst)
    print(f"Installed: {dst}")

print("\n[4] Testing deployed DatasmithWorker on port 19850...")
proc = subprocess.Popen(
    [deployed_exe, "19850", "IngeTrazo LiveSync"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
)
time.sleep(1.8)

try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3.0)
    s.connect(("127.0.0.1", 19850))
    s.sendall(b'{"cmd":"PING"}\n')
    data = s.recv(4096)
    print("PING Response:", data.decode("utf-8-sig").strip())
    
    # Send STOP
    s.sendall(b'{"cmd":"STOP"}\n')
    data = s.recv(4096)
    print("STOP Response:", data.decode("utf-8-sig").strip())
    s.close()
    print("[SUCCESS] Deployed worker responds correctly on port 19850!")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except Exception:
        pass

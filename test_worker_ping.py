"""
Verify DatasmithWorker.exe starts with Messaging and handles IPC
"""
import subprocess
import socket
import time
import json
import os

worker_exe = r"f:\igz-tm-livesync\DatasmithWorker.exe"

print(f"Starting {worker_exe}...")
proc = subprocess.Popen(
    [worker_exe, "19859", "Test_IngeTrazo"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
)

time.sleep(2.0)

for attempt in range(1, 10):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(3.0)
        s.connect(("127.0.0.1", 19859))
        break
    except Exception:
        time.sleep(0.5)

try:
    s.sendall(b'{"cmd":"PING"}\n')
    data = s.recv(4096)
    print("PING Response:", data.decode("utf-8-sig").strip())
    
    s.sendall(b'{"cmd":"SYNC"}\n')
    data = s.recv(4096)
    print("SYNC Response:", data.decode("utf-8-sig").strip())

    s.sendall(b'{"cmd":"STOP"}\n')
    data = s.recv(4096)
    print("STOP Response:", data.decode("utf-8-sig").strip())
    s.close()
finally:
    proc.terminate()
    stdout, stderr = proc.communicate(timeout=3)
    print("Worker stdout:")
    print(stdout.decode("utf-8", errors="ignore"))
    if stderr:
        print("Worker stderr:")
        print(stderr.decode("utf-8", errors="ignore"))

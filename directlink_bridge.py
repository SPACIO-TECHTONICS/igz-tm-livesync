"""
Epic Games Datasmith DirectLink Protocol Bridge for IngeTrazo.
Integrates directly with DatasmithWorker.exe (C# background worker)
and DatasmithFacadeCSharp.dll runtime to register live DirectLink endpoints
recognized by Twinmotion.
"""

import os
import sys
import json
import time
import socket
import struct
import tempfile
import subprocess
import threading
from typing import Optional, Dict, Any, Tuple, Callable

from mesh_exporter import SceneExportData, MeshData, MaterialData

RHINO_DATASMITH_DIR = r"C:\ProgramData\McNeel\Rhinoceros\7.0\Plug-ins\Datasmith Rhino Exporter (d1fdc795-b334-4933-b680-088119cdc6bb)"


class DirectLinkBridge:
    """
    DirectLink Source Bridge for Twinmotion.
    Manages DatasmithWorker.exe background process and TCP IPC communication.
    """

    def __init__(self, source_name: str = "IngeTrazo LiveSync", stream_name: str = "IngeTrazo Scene", port: int = 19850):
        self.source_name = source_name
        self.stream_name = stream_name
        self.port = port
        self.is_connected = False
        self.worker_process: Optional[subprocess.Popen] = None
        self._sock: Optional[socket.socket] = None

        self.last_sync_time: float = 0.0
        self.snapshot_index: int = 0

        # Cache directory matching DatasmithWorker
        self.cache_dir = os.path.join(tempfile.gettempdir(), "IngeTrazo_DirectLink")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _log(self, msg: str, log_cb: Optional[Callable[[str], None]] = None):
        """Unified logging to callback and stdout."""
        print(f"[DirectLinkBridge] {msg}")
        if log_cb and callable(log_cb):
            try:
                log_cb(msg)
            except Exception:
                pass

    def _find_worker_exe(self) -> Optional[str]:
        """Locates DatasmithWorker.exe in plugin directory or workspace."""
        current_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(current_dir, "DatasmithWorker.exe"),
            os.path.expandvars(r"%APPDATA%\ingetrazo\plugins\igz_tm_livesync\DatasmithWorker.exe"),
            r"F:\igz-tm-livesync\DatasmithWorker.exe"
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
        return None

    def start_endpoint(self, log_cb: Optional[Callable[[str], None]] = None) -> bool:
        """Starts DatasmithWorker.exe and verifies IPC connection."""
        if self.is_connected and self._sock:
            self._log("DirectLink worker already connected.", log_cb)
            return True

        worker_exe = self._find_worker_exe()
        if not worker_exe:
            err = f"DatasmithWorker.exe not found in plugin paths. Checked: {self._find_worker_exe()}"
            self._log(f"ERROR: {err}", log_cb)
            return False

        self._log(f"Using worker binary: {worker_exe}", log_cb)

        # 1. Start worker process if not already running
        if self.worker_process is None or self.worker_process.poll() is not None:
            try:
                self._log(f"Spawning background worker on port {self.port} (Source: '{self.source_name}')...", log_cb)
                self.worker_process = subprocess.Popen(
                    [worker_exe, str(self.port), self.source_name],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
                time.sleep(1.2)  # Give time to boot and load native Datasmith
            except Exception as e:
                self._log(f"ERROR: Failed to launch DatasmithWorker.exe: {e}", log_cb)
                return False

        # Check if worker exited prematurely
        exit_code = self.worker_process.poll()
        if exit_code is not None:
            stdout_out = self.worker_process.stdout.read().decode('utf-8', errors='ignore') if self.worker_process.stdout else ""
            stderr_out = self.worker_process.stderr.read().decode('utf-8', errors='ignore') if self.worker_process.stderr else ""
            self._log(f"ERROR: DatasmithWorker exited with code {exit_code}.\nOutput: {stdout_out}\nError: {stderr_out}", log_cb)
            return False

        # 2. Connect to worker via TCP loopback
        self._log(f"Connecting to worker IPC at 127.0.0.1:{self.port}...", log_cb)
        for attempt in range(1, 6):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2.5)
                s.connect(("127.0.0.1", self.port))
                self._sock = s
                
                # Send PING
                response = self._send_command({"cmd": "PING"}, log_cb)
                if response and response.get("status") == "OK":
                    self.is_connected = True
                    ready_state = response.get("datasmithReady", False)
                    self._log(f"Connected to DatasmithWorker (attempt {attempt}). Datasmith ready: {ready_state}", log_cb)
                    return True
            except Exception as e:
                self._log(f"Connection attempt {attempt}/5: {e}", log_cb)
                time.sleep(0.6)

        self._log("ERROR: Could not establish TCP connection to DatasmithWorker.exe", log_cb)
        return False

    def _send_command(self, payload: Dict[str, Any], log_cb: Optional[Callable[[str], None]] = None) -> Optional[Dict[str, Any]]:
        """Sends a JSON command to DatasmithWorker.exe and parses JSON response."""
        if not self._sock:
            return None
        try:
            msg = json.dumps(payload) + "\n"
            self._sock.sendall(msg.encode("utf-8"))
            
            # Read single response line
            data = b""
            while not data.endswith(b"\n"):
                chunk = self._sock.recv(4096)
                if not chunk:
                    break
                data += chunk
            
            if data:
                text = data.decode("utf-8-sig", errors="ignore").strip()
                res = json.loads(text)
                return res
        except Exception as e:
            self._log(f"IPC communication error: {e}", log_cb)
            self.is_connected = False
        return None

    def publish_snapshot(self, scene_data: SceneExportData, log_cb: Optional[Callable[[str], None]] = None) -> bool:
        """Pushes scene snapshot to Twinmotion via Datasmith DirectLink."""
        self.snapshot_index += 1
        self.last_sync_time = time.time()

        # 1. Write binary geometry file for DatasmithWorker
        bin_file = os.path.join(self.cache_dir, "scene_geometry.bin")
        try:
            with open(bin_file, "wb") as f:
                f.write(struct.pack("<I", len(scene_data.meshes)))
                for m in scene_data.meshes:
                    name_bytes = m.name.encode("utf-8")
                    f.write(struct.pack("<H", len(name_bytes)) + name_bytes)

                    num_verts = len(m.vertices) // 3
                    f.write(struct.pack("<I", num_verts))
                    for i in range(num_verts):
                        f.write(struct.pack("<fff", m.vertices[i*3], m.vertices[i*3+1], m.vertices[i*3+2]))

                    all_indices = []
                    for sm in m.submeshes:
                        all_indices.extend(sm.indices)
                    num_tris = len(all_indices) // 3
                    f.write(struct.pack("<I", num_tris))
                    for i in range(num_tris):
                        f.write(struct.pack("<iii", all_indices[i*3], all_indices[i*3+1], all_indices[i*3+2]))
            self._log(f"Cached binary geometry: {os.path.basename(bin_file)} ({len(scene_data.meshes)} meshes)", log_cb)
        except Exception as e:
            self._log(f"Warning writing binary geometry: {e}", log_cb)

        # 2. Ensure worker endpoint is active
        if not self.is_connected:
            self._log("Worker not connected. Starting endpoint...", log_cb)
            if not self.start_endpoint(log_cb):
                self._log("ERROR: Could not start DirectLink endpoint.", log_cb)
                return False

        # 3. Transmit SYNC command to worker
        self._log(f"Transmitting SYNC command with geometry (snapshot #{self.snapshot_index})...", log_cb)
        response = self._send_command({"cmd": "SYNC", "file": bin_file, "snapshot": self.snapshot_index}, log_cb)
        if response:
            if response.get("status") == "OK":
                synced = response.get("synced", True)
                self._log(f"DatasmithWorker SYNC confirmed (snapshot #{self.snapshot_index}, synced={synced}).", log_cb)
                return True
            else:
                self._log(f"ERROR: DatasmithWorker returned error: {response.get('message')}", log_cb)
                return False

        self._log("ERROR: No response received from DatasmithWorker on SYNC.", log_cb)
        return False

    def send_camera_update(self, camera_pos: Tuple[float, float, float], target: Tuple[float, float, float], fov: float) -> bool:
        """Streams live perspective camera to Twinmotion."""
        if not self.is_connected:
            return False

        payload = {
            "cmd": "CAMERA",
            "pos": list(camera_pos),
            "target": list(target),
            "fov": fov
        }
        response = self._send_command(payload)
        return bool(response and response.get("status") == "OK")

    def stop_endpoint(self, log_cb: Optional[Callable[[str], None]] = None):
        """Cleans up DirectLink handles and stops background worker."""
        if self._sock:
            try:
                self._send_command({"cmd": "STOP"}, log_cb)
                self._sock.close()
            except Exception:
                pass
            self._sock = None

        if self.worker_process:
            try:
                self.worker_process.terminate()
                self.worker_process.wait(timeout=2)
            except Exception:
                try:
                    self.worker_process.kill()
                except Exception:
                    pass
            self.worker_process = None

        self.is_connected = False
        self._log("DirectLink worker stopped.", log_cb)

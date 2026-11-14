"""
IngeTrazo Extension: Twinmotion LiveSync (DirectLink)
Reference implementation combining:
1. knTMSync (Rhino): Sequential 'TM Option N' Layer State Management & Safe Viewport/Object Recovery.
2. hamzah1985/ingetrazo-twinmotion-sync: DirectLink integration, DCC Camera Sync, and native worker support.

Features:
- Sequential 'TM Option N' Layer State Management with numerical sorting.
- Viewport camera and working layer visibility preservation.
- Temporary unhiding of objects on active export layers.
- Real-time Datasmith DirectLink publishing to Twinmotion.
- Live DCC Camera Sync (streams perspective view at ~25-28 fps).
- Embedded PySide6 UI panel for the IngeTrazo side tray.
"""

import os
import re
import sys
import copy
import traceback
from typing import List, Dict, Tuple, Optional, Any, Callable

# Ensure extension directory is on sys.path for local module resolution
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

# IngeTrazo Tool base class binding
try:
    from tools.base import Tool
except ImportError:
    class Tool:
        name = "Twinmotion LiveSync"
        shortcut = None
        description = "LiveSync with Twinmotion"
        def on_activate(self, viewport): pass
        def on_deactivate(self, viewport): pass

# Qt GUI bindings (PySide6 standard for IngeTrazo)
try:
    import PySide6.QtSvg
except ImportError:
    try:
        import PyQt6.QtSvg
    except ImportError:
        pass

try:
    from PySide6.QtCore import Qt, QTimer, Signal, QObject
    from PySide6.QtGui import QIcon, QAction
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
        QPushButton, QCheckBox, QTextEdit, QGroupBox, QMessageBox, QToolBar
    )
except ImportError:
    try:
        from PyQt6.QtCore import Qt, QTimer, pyqtSignal as Signal, QObject
        from PyQt6.QtGui import QIcon, QAction
        from PyQt6.QtWidgets import (
            QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
            QPushButton, QCheckBox, QTextEdit, QGroupBox, QMessageBox, QToolBar
        )
    except ImportError:
        class QWidget: pass
        class QObject: pass
        class QToolBar: pass
        class QIcon:
            def __init__(self, *args): pass
            def isNull(self): return False
        class QAction:
            def __init__(self, *args): pass
            def setCheckable(self, val): pass
            def setText(self, val): pass
        class Signal:
            def __init__(self, *args): pass
            def emit(self, *args): pass
            def connect(self, fn): pass

from mesh_exporter import IngeTrazoMeshExtractor
from directlink_bridge import DirectLinkBridge


# ---------------------------------------------------------------------------
# Configuration Loader (.env)
# ---------------------------------------------------------------------------
def load_env_config() -> Dict[str, str]:
    """Loads environment configuration without external dependencies."""
    config = {
        "DIRECTLINK_HOST": "127.0.0.1",
        "DIRECTLINK_PORT": "6666",
        "DIRECTLINK_SOURCE_NAME": "IngeTrazo",
        "DIRECTLINK_STREAM_NAME": "IngeTrazo LiveSync",
        "DIRECTLINK_UNIT_SCALE": "100.0"
    }
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.isfile(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        config[k.strip()] = v.strip()
        except Exception:
            pass
    return config


ENV_CONFIG = load_env_config()


# ---------------------------------------------------------------------------
# Core Option Management (Ported from knTMSync)
# ---------------------------------------------------------------------------
class TMSyncManager:
    """
    Manages TM Option presets, layer states, and viewport restoration.
    Maintains exact functional parity with knTMSync.
    """

    OPTION_PATTERN = re.compile(r"^TM Option (\d+)$", re.IGNORECASE)
    DOCUMENT_STORAGE_KEY = "tm_sync_options"

    @classmethod
    def get_existing_tm_options(cls, app: Any) -> List[str]:
        """Retrieves and numerically sorts all existing 'TM Option N' layer states."""
        options_dict = cls._get_stored_options(app)
        if not options_dict:
            return []

        parsed = []
        for name in options_dict.keys():
            match = cls.OPTION_PATTERN.match(name.strip())
            if match:
                parsed.append((int(match.group(1)), name.strip()))

        # Sort numerically by option number (Option 2 before Option 10)
        parsed.sort(key=lambda item: item[0])
        return [item[1] for item in parsed]

    @classmethod
    def get_next_tm_option_name(cls, tm_options: List[str]) -> str:
        """Calculates the next available 'TM Option N' name."""
        if not tm_options:
            return "TM Option 1"

        max_n = 0
        for name in tm_options:
            match = cls.OPTION_PATTERN.match(name.strip())
            if match:
                n = int(match.group(1))
                if n > max_n:
                    max_n = n

        return f"TM Option {max_n + 1}"

    @classmethod
    def save_or_update_option(cls, app: Any, option_name: str) -> bool:
        """Saves or updates a Named Layer State from current document visibility."""
        doc_options = cls._get_stored_options(app)
        current_layer_states = cls._capture_active_layer_states(app)

        doc_options[option_name] = current_layer_states
        cls._set_stored_options(app, doc_options)
        cls._log(app, f"Saved Layer State: '{option_name}'")
        return True

    @classmethod
    def _capture_active_layer_states(cls, app: Any) -> Dict[str, bool]:
        """Captures the visible state of all scene layers."""
        states = {}
        scene = getattr(app, "scene", None)
        if scene and hasattr(scene, "layers"):
            for layer in scene.layers:
                layer_name = getattr(layer, "name", str(layer))
                is_vis = getattr(layer, "visible", True)
                states[layer_name] = bool(is_vis)
        return states

    @classmethod
    def _apply_layer_states(cls, app: Any, states: Dict[str, bool]):
        """Applies visibility states to scene layers."""
        scene = getattr(app, "scene", None)
        if scene and hasattr(scene, "layers"):
            for layer in scene.layers:
                layer_name = getattr(layer, "name", str(layer))
                if layer_name in states:
                    if hasattr(layer, "visible"):
                        layer.visible = states[layer_name]
                    elif hasattr(layer, "set_visible"):
                        layer.set_visible(states[layer_name])

    @classmethod
    def _get_stored_options(cls, app: Any) -> Dict[str, Any]:
        """Gets persistent options dictionary from active IngeTrazo document."""
        if hasattr(app, "document_data"):
            doc_data = app.document_data(default={})
            return doc_data.get(cls.DOCUMENT_STORAGE_KEY, {})
        return {}

    @classmethod
    def _set_stored_options(cls, app: Any, options_dict: Dict[str, Any]):
        """Persists the options dictionary into the active IngeTrazo document."""
        if hasattr(app, "document_data") and hasattr(app, "set_document_data"):
            doc_data = copy.deepcopy(app.document_data(default={}))
            doc_data[cls.DOCUMENT_STORAGE_KEY] = options_dict
            app.set_document_data(doc_data)

    @classmethod
    def _log(cls, app: Any, msg: str):
        """Outputs log messages to IngeTrazo viewport or status bar."""
        formatted = f"[IngeTrazo-TMSync] {msg}"
        print(formatted)
        if hasattr(app, "viewport") and hasattr(app.viewport, "flash_status"):
            app.viewport.flash_status(formatted, 3000)


# ---------------------------------------------------------------------------
# Synchronization Engine with knTMSync try...finally Restoration
# ---------------------------------------------------------------------------
def resolve_context(app: Any) -> Tuple[Optional[Any], Optional[Any]]:
    """Robustly discovers IngeTrazo viewport and scene across diverse app structures."""
    viewport = getattr(app, "viewport", None)
    scene = getattr(app, "scene", None)

    # 1. Check window attributes
    window = getattr(app, "window", None)
    if not window and hasattr(app, "main_window"):
        window = getattr(app, "main_window")

    if window:
        if not viewport and hasattr(window, "viewport"):
            viewport = getattr(window, "viewport")
        if not scene:
            scene = getattr(window, "scene", getattr(window, "model", getattr(window, "document", None)))

    # 2. Check viewport attributes
    if viewport and not scene:
        scene = getattr(viewport, "scene", getattr(viewport, "model", getattr(viewport, "document", None)))

    # 3. Check document / model attributes on app
    if not scene:
        for attr in ("model", "document", "doc", "active_document", "project"):
            candidate = getattr(app, attr, None)
            if candidate:
                scene = getattr(candidate, "scene", candidate)
                break

    # 4. Search PySide6 topLevelWidgets
    if not viewport or not scene:
        try:
            from PySide6.QtWidgets import QApplication
            for widget in QApplication.topLevelWidgets():
                if not viewport and hasattr(widget, "viewport"):
                    viewport = getattr(widget, "viewport")
                if not scene:
                    for attr in ("scene", "model", "document"):
                        if hasattr(widget, attr):
                            scene = getattr(widget, attr)
                            break
        except Exception:
            pass

    return viewport, scene


class TMSyncEngine:
    """
    Executes Datasmith Direct Link synchronization while preserving
    viewport camera, working layer states, and unhidden object visibility.
    """

    def __init__(self, bridge: DirectLinkBridge):
        self.bridge = bridge
        scale_val = float(ENV_CONFIG.get("DIRECTLINK_UNIT_SCALE", "100.0"))
        self.extractor = IngeTrazoMeshExtractor(unit_scale=scale_val)

    def execute_sync(self, app: Any, target_state: str, log_cb: Optional[Callable[[str], None]] = None) -> bool:
        """
        Executes synchronization following the knTMSync safe recovery protocol.
        """
        def log(msg: str):
            TMSyncManager._log(app, msg)
            if log_cb and callable(log_cb):
                try:
                    log_cb(msg)
                except Exception:
                    pass

        log(f"[1/5] Resolving 3D environment for '{target_state}'...")
        viewport, scene = resolve_context(app)

        if not viewport or not scene:
            err_msg = (
                f"[ERROR] Could not resolve IngeTrazo viewport or scene.\n"
                f"  - App type: {type(app).__name__}\n"
                f"  - Viewport resolved: {type(viewport).__name__ if viewport else 'None'}\n"
                f"  - Scene resolved: {type(scene).__name__ if scene else 'None'}\n"
                f"  - App attributes: {[a for a in dir(app) if not a.startswith('_')][:15]}"
            )
            log(err_msg)
            return False

        log(f"[2/5] Viewport: {type(viewport).__name__}, Scene: {type(scene).__name__}")
        attrs = [a for a in dir(scene) if not a.startswith('_')]
        log(f"Scene members: {attrs[:12]}")

        # 1. Push / snapshot active camera projection
        saved_camera = None
        if hasattr(viewport, "camera"):
            saved_camera = copy.deepcopy(viewport.camera)
        elif hasattr(viewport, "get_view_state"):
            saved_camera = viewport.get_view_state()

        # 2. Snapshot current working layer states
        working_layer_cache = TMSyncManager._capture_active_layer_states(app)
        temporarily_unhidden_entities = []

        try:
            # 3. Apply target Layer State visibility
            stored_options = TMSyncManager._get_stored_options(app)
            target_layers = stored_options.get(target_state, {})
            if target_layers:
                log(f"Applying stored layer visibility for '{target_state}' ({len(target_layers)} layers)...")
                TMSyncManager._apply_layer_states(app, target_layers)
                active_layer_names = [k for k, v in target_layers.items() if v]
            else:
                log(f"No custom layer filter defined for '{target_state}'. Exporting all active visible layers.")
                active_layer_names = None

            # 4. Temporarily unhide objects on active export layers
            if active_layer_names is not None:
                entities = self.extractor._get_scene_entities(scene)
                for ent in entities:
                    ent_layer = self.extractor._get_entity_layer(ent)
                    if ent_layer in active_layer_names:
                        is_hidden = False
                        if hasattr(ent, "visible") and not ent.visible:
                            is_hidden = True
                            ent.visible = True
                        elif hasattr(ent, "is_visible") and callable(ent.is_visible) and not ent.is_visible():
                            is_hidden = True
                            if hasattr(ent, "show"):
                                ent.show()

                        if is_hidden:
                            temporarily_unhidden_entities.append(ent)

                if temporarily_unhidden_entities:
                    log(f"Temporarily unhid {len(temporarily_unhidden_entities)} object(s) on active export layers.")

            # Redraw before extraction
            if hasattr(viewport, "redraw"):
                viewport.redraw()
            elif hasattr(viewport, "update"):
                viewport.update()

            # 5. Extract scene mesh data
            log("[3/5] Extracting 3D geometry and materials...")
            all_entities = self.extractor._get_scene_entities(scene)
            log(f"Scanning {len(all_entities)} entities in scene...")
            scene_data = self.extractor.extract_scene(scene, active_layer_names=active_layer_names)
            log(f"Extracted {len(scene_data.meshes)} mesh(es), {len(scene_data.materials)} material(s).")

            if len(scene_data.meshes) == 0:
                log("[WARN] Scene contains 0 visible meshes. Please ensure your model contains 3D geometry.")

            # 6. Execute Datasmith Direct Link snapshot publish
            log("[4/5] Transmitting snapshot to Twinmotion via DirectLink...")
            success = self.bridge.publish_snapshot(scene_data, log_cb=log)
            if success:
                log(f"[5/5] SUCCESS: '{target_state}' successfully synchronized to Twinmotion!")
            else:
                log("[ERROR] DirectLink snapshot transmission failed. See worker logs above.")

            return success

        except Exception as exc:
            err_trace = traceback.format_exc()
            log(f"[ERROR] Exception during synchronization:\n{type(exc).__name__}: {exc}\n{err_trace}")
            return False

        finally:
            # 7. Re-hide all temporarily unhidden objects
            if temporarily_unhidden_entities:
                for ent in temporarily_unhidden_entities:
                    if hasattr(ent, "visible"):
                        ent.visible = False
                    elif hasattr(ent, "hide"):
                        ent.hide()

            # 8. Restore working camera projection
            if saved_camera is not None:
                if hasattr(viewport, "camera"):
                    viewport.camera = saved_camera
                elif hasattr(viewport, "set_view_state"):
                    viewport.set_view_state(saved_camera)

            # 9. Restore working layer visibility exactly as it was
            TMSyncManager._apply_layer_states(app, working_layer_cache)

            # 10. Viewport redraw
            if hasattr(viewport, "redraw"):
                viewport.redraw()
            elif hasattr(viewport, "update"):
                viewport.update()

            log("Viewport, working layers, and hidden objects restored.")


# ---------------------------------------------------------------------------
# PySide6 UI Dock Panel
# ---------------------------------------------------------------------------
class TMSyncDockPanel(QWidget):
    """
    Side panel widget for IngeTrazo.
    Allows selection, creation, and updating of TM Option states.
    Features live DCC Camera Sync matching hamzah1985/ingetrazo-twinmotion-sync.
    Complies with UI styling rules: No blue colors or blue gradients.
    """

    def __init__(self, app: Any, engine: TMSyncEngine, parent=None):
        super().__init__(parent)
        self.app = app
        self.engine = engine
        self._init_ui()
        self._refresh_options()

        # Auto-sync timer (debounced)
        self.auto_sync_timer = QTimer(self)
        self.auto_sync_timer.setSingleShot(True)
        self.auto_sync_timer.setInterval(1500)
        self.auto_sync_timer.timeout.connect(self._on_auto_sync_trigger)

        # Camera sync timer (~28 updates/sec for live DCC Camera Sync)
        self.camera_timer = QTimer(self)
        self.camera_timer.setInterval(35)
        self.camera_timer.timeout.connect(self._stream_camera_update)

    def _init_ui(self):
        """Constructs panel layout with dark-neutral styling (no blue)."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Style sheet: Dark slate & neutral gray palette with emerald accent (NO BLUE)
        self.setStyleSheet("""
            QWidget {
                background-color: #242424;
                color: #e0e0e0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                font-size: 12px;
            }
            QGroupBox {
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                margin-top: 8px;
                padding-top: 10px;
                font-weight: bold;
                color: #a3a3a3;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding-left: 6px;
                padding-right: 6px;
            }
            QComboBox {
                background-color: #1a1a1a;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 6px;
                color: #ffffff;
            }
            QComboBox:hover {
                border-color: #555555;
            }
            QPushButton {
                background-color: #333333;
                border: 1px solid #4a4a4a;
                border-radius: 4px;
                padding: 8px;
                color: #ffffff;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #3f3f3f;
                border-color: #666666;
            }
            QPushButton#syncButton {
                background-color: #059669; /* Emerald Green */
                border: 1px solid #10b981;
                font-weight: bold;
                font-size: 13px;
                padding: 10px;
            }
            QPushButton#syncButton:hover {
                background-color: #10b981;
            }
            QCheckBox {
                color: #cccccc;
            }
            QTextEdit {
                background-color: #181818;
                border: 1px solid #333333;
                border-radius: 4px;
                color: #9ca3af;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
        """)

        # 1. Connection Status
        status_box = QGroupBox("DirectLink Status", self)
        status_layout = QVBoxLayout(status_box)
        self.status_label = QLabel("● DirectLink Active (UDP 6666 / IPC 19850)", self)
        self.status_label.setStyleSheet("color: #10b981; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        layout.addWidget(status_box)

        # 2. Options Management (knTMSync workflow)
        options_box = QGroupBox("Twinmotion Options", self)
        options_layout = QVBoxLayout(options_box)

        options_layout.addWidget(QLabel("Select Option to Sync:", self))
        self.options_combo = QComboBox(self)
        options_layout.addWidget(self.options_combo)

        btn_layout = QHBoxLayout()
        self.btn_create_next = QPushButton("+ Create Next Option", self)
        self.btn_create_next.clicked.connect(self._on_create_next_option)
        btn_layout.addWidget(self.btn_create_next)

        self.btn_update_opt = QPushButton("Update from Viewport", self)
        self.btn_update_opt.clicked.connect(self._on_update_current_option)
        btn_layout.addWidget(self.btn_update_opt)
        options_layout.addLayout(btn_layout)

        layout.addWidget(options_box)

        # 3. Synchronization & Live Tracking Controls
        sync_box = QGroupBox("Synchronization & Camera", self)
        sync_layout = QVBoxLayout(sync_box)

        self.btn_sync = QPushButton("⚡ Sync to Twinmotion", self)
        self.btn_sync.setObjectName("syncButton")
        self.btn_sync.clicked.connect(self._on_sync_clicked)
        sync_layout.addWidget(self.btn_sync)

        self.chk_auto_sync = QCheckBox("Auto-Sync on Scene Modification", self)
        self.chk_auto_sync.stateChanged.connect(self._on_auto_sync_toggled)
        sync_layout.addWidget(self.chk_auto_sync)

        # Live Camera Sync (Twinmotion DCC Camera Sync)
        self.chk_camera_sync = QCheckBox("🎥 DCC Camera Sync (Twinmotion Follows Viewport)", self)
        self.chk_camera_sync.stateChanged.connect(self._on_camera_sync_toggled)
        sync_layout.addWidget(self.chk_camera_sync)

        # Toolbar Visibility Control
        self.btn_show_toolbar = QPushButton("🖥️ Show / Dock Toolbar", self)
        self.btn_show_toolbar.clicked.connect(self._on_show_toolbar_clicked)
        sync_layout.addWidget(self.btn_show_toolbar)

        layout.addWidget(sync_box)

        # 4. Activity Log
        log_box = QGroupBox("Activity Log", self)
        log_layout = QVBoxLayout(log_box)
        self.log_text = QTextEdit(self)
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(130)
        log_layout.addWidget(self.log_text)
        layout.addWidget(log_box)

        layout.addStretch()

    def _refresh_options(self):
        """Refreshes the dropdown list with sorted TM Option presets."""
        self.options_combo.clear()
        options = TMSyncManager.get_existing_tm_options(self.app)

        if not options:
            next_name = TMSyncManager.get_next_tm_option_name([])
            self.options_combo.addItem(f"{next_name} (New)")
            self.btn_create_next.setText(f"[+ Create '{next_name}']")
        else:
            for opt in options:
                self.options_combo.addItem(opt)
            next_name = TMSyncManager.get_next_tm_option_name(options)
            self.btn_create_next.setText(f"[+ Create '{next_name}']")

    def _on_create_next_option(self):
        options = TMSyncManager.get_existing_tm_options(self.app)
        next_name = TMSyncManager.get_next_tm_option_name(options)
        TMSyncManager.save_or_update_option(self.app, next_name)
        self._add_log(f"Created preset: {next_name}")
        self._refresh_options()
        self.options_combo.setCurrentText(next_name)

    def _on_update_current_option(self):
        current_text = self.options_combo.currentText()
        clean_name = current_text.replace(" (New)", "").strip()
        if clean_name:
            TMSyncManager.save_or_update_option(self.app, clean_name)
            self._add_log(f"Updated preset: '{clean_name}' from current viewport.")
            self._refresh_options()
            self.options_combo.setCurrentText(clean_name)

    def _on_sync_clicked(self):
        current_text = self.options_combo.currentText()
        target_name = current_text.replace(" (New)", "").strip()
        if not target_name:
            target_name = TMSyncManager.get_next_tm_option_name([])
            TMSyncManager.save_or_update_option(self.app, target_name)
            self._refresh_options()

        self._add_log(f"\n--- Starting sync for '{target_name}' ---")
        success = self.engine.execute_sync(self.app, target_name, log_cb=self._add_log)
        if success:
            self._add_log(f"--- [OK] Sync for '{target_name}' finished successfully! ---")
        else:
            self._add_log(f"--- [FAILED] Sync for '{target_name}' failed. Review details above. ---")

    def _on_auto_sync_toggled(self, state):
        if state == Qt.CheckState.Checked.value or state == 2:
            self._add_log("Auto-Sync enabled.")
            if hasattr(self.app, "on_document_changed"):
                self.app.on_document_changed(self._on_document_changed)
        else:
            self._add_log("Auto-Sync disabled.")

    def _on_camera_sync_toggled(self, state):
        if state == Qt.CheckState.Checked.value or state == 2:
            self._add_log("DCC Camera Sync started (~28 fps).")
            self.camera_timer.start()
        else:
            self._add_log("DCC Camera Sync stopped.")
            self.camera_timer.stop()

    def _stream_camera_update(self):
        """Streams perspective camera changes to Twinmotion."""
        viewport = getattr(self.app, "viewport", None)
        if not viewport:
            return

        pos = (0.0, -10.0, 5.0)
        target = (0.0, 0.0, 0.0)
        fov = 60.0

        if hasattr(viewport, "camera"):
            cam = viewport.camera
            raw_pos = getattr(cam, "position", pos)
            raw_tgt = getattr(cam, "target", target)
            raw_fov = getattr(cam, "fov", fov)
            pos = self.engine.extractor._get_xyz(raw_pos)
            target = self.engine.extractor._get_xyz(raw_tgt)
            try:
                fov = float(raw_fov() if callable(raw_fov) else raw_fov)
            except Exception:
                fov = 60.0

        self.engine.bridge.send_camera_update(camera_pos=pos, target=target, fov=fov)

    def _on_document_changed(self):
        if self.chk_auto_sync.isChecked():
            self.auto_sync_timer.start()

    def _on_auto_sync_trigger(self):
        self._on_sync_clicked()

    def _add_log(self, text: str):
        self.log_text.append(text)

    def _on_show_toolbar_clicked(self):
        global _GLOBAL_TOOLBAR, _GLOBAL_ENGINE
        if not _GLOBAL_TOOLBAR and _GLOBAL_ENGINE:
            _GLOBAL_TOOLBAR = setup_toolbar(self.app, _GLOBAL_ENGINE, self)
        if _GLOBAL_TOOLBAR:
            _GLOBAL_TOOLBAR.setVisible(True)
            _GLOBAL_TOOLBAR.show()
            _GLOBAL_TOOLBAR.raise_()
            self._add_log("Toolbar displayed on window.")
            if hasattr(self.app, "restore_toolbar_layout"):
                try:
                    self.app.restore_toolbar_layout()
                except Exception:
                    pass
        else:
            self._add_log("Could not resolve main window for toolbar.")


# ---------------------------------------------------------------------------
# IngeTrazo Tool Implementation
# ---------------------------------------------------------------------------
class TMSyncTool(Tool):
    """
    Primary IngeTrazo Tool class discovered by IngeTrazo's plugin scanner.
    Appears under Extensions -> Twinmotion LiveSync.
    """
    name = "Twinmotion LiveSync"
    shortcut = "Ctrl+Shift+T"
    description = "Synchronize geometry, layers, and camera with Twinmotion via Datasmith Direct Link."

    def on_activate(self, viewport):
        global _GLOBAL_BRIDGE, _GLOBAL_ENGINE, _GLOBAL_PANEL, _GLOBAL_TOOLBAR

        # Extract app reference from viewport or window context
        app = getattr(viewport, "app", None)
        if not app:
            app = getattr(viewport, "window", None)
        if not app:
            class ProxyApp: pass
            app = ProxyApp()
            app.viewport = viewport
            app.scene = getattr(viewport, "scene", None)
            app.window = getattr(viewport, "window", None)

        if _GLOBAL_BRIDGE is None:
            setup(app)

        if not _GLOBAL_TOOLBAR and _GLOBAL_ENGINE:
            _GLOBAL_TOOLBAR = setup_toolbar(app, _GLOBAL_ENGINE, _GLOBAL_PANEL)

        if _GLOBAL_TOOLBAR:
            _GLOBAL_TOOLBAR.setVisible(True)
            _GLOBAL_TOOLBAR.show()
            _GLOBAL_TOOLBAR.raise_()

        if _GLOBAL_PANEL:
            _GLOBAL_PANEL.show()
            _GLOBAL_PANEL.raise_()

        if hasattr(viewport, "flash_status"):
            viewport.flash_status("Twinmotion LiveSync active", 3000)

    def on_deactivate(self, viewport):
        pass


# ---------------------------------------------------------------------------
# IngeTrazo Plugin Lifecycle Hook & Toolbar
# ---------------------------------------------------------------------------
_GLOBAL_BRIDGE: Optional[DirectLinkBridge] = None
_GLOBAL_ENGINE: Optional[TMSyncEngine] = None
_GLOBAL_PANEL: Optional[TMSyncDockPanel] = None
_GLOBAL_TOOLBAR: Any = None


def get_main_window(app: Any) -> Any:
    """Robustly locates IngeTrazo's QMainWindow across multiple context structures."""
    candidates = [
        getattr(app, "window", None),
        getattr(app, "main_window", None),
    ]

    viewport = getattr(app, "viewport", None)
    if viewport:
        candidates.append(getattr(viewport, "window", None))
        if hasattr(viewport, "window") and callable(viewport.window):
            try:
                candidates.append(viewport.window())
            except Exception:
                pass
        if hasattr(viewport, "nativeParentWidget") and callable(viewport.nativeParentWidget):
            try:
                candidates.append(viewport.nativeParentWidget())
            except Exception:
                pass

    # Check Qt QApplication top-level widgets for QMainWindow
    try:
        from PySide6.QtWidgets import QApplication, QMainWindow
        for w in QApplication.topLevelWidgets():
            if isinstance(w, QMainWindow):
                candidates.append(w)
    except Exception:
        pass

    for c in candidates:
        if c and hasattr(c, "addToolBar"):
            return c
    return None


def setup_toolbar(app: Any, engine: TMSyncEngine, panel: Optional[TMSyncDockPanel] = None) -> Any:
    """Creates a native toolbar with custom SVG icons in IngeTrazo."""
    window = get_main_window(app)
    if not window:
        return None

    # Check if toolbar already exists
    if hasattr(window, "findChildren"):
        try:
            for child in window.findChildren(QToolBar):
                if child.objectName() == "igz_tm_livesync_toolbar":
                    child.setVisible(True)
                    child.show()
                    return child
        except Exception:
            pass

    icons_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
    toolbar = window.addToolBar("Twinmotion LiveSync")
    toolbar.setObjectName("igz_tm_livesync_toolbar")
    if hasattr(toolbar, "setMovable"):
        toolbar.setMovable(True)

    # Connect Action
    icon_connect = QIcon(os.path.join(icons_dir, "tm_connect.svg"))
    act_connect = QAction(icon_connect, "Connect", toolbar)
    act_connect.setToolTip("Start DirectLink Beacon (UDP 6666)")
    act_connect.triggered.connect(lambda: engine.bridge.start_endpoint(log_cb=panel._add_log if panel else None))
    toolbar.addAction(act_connect)

    # Sync Now Action
    icon_sync = QIcon(os.path.join(icons_dir, "tm_sync.svg"))
    act_sync = QAction(icon_sync, "Sync Now", toolbar)
    act_sync.setToolTip("Sync current model to Twinmotion")
    if panel:
        act_sync.triggered.connect(panel._on_sync_clicked)
    toolbar.addAction(act_sync)

    # Create Option Action
    icon_opt = QIcon(os.path.join(icons_dir, "tm_create_option.svg"))
    act_opt = QAction(icon_opt, "Option +", toolbar)
    act_opt.setToolTip("Create next sequential TM Option preset")
    if panel:
        act_opt.triggered.connect(panel._on_create_next_option)
    toolbar.addAction(act_opt)

    # Camera Sync Action
    icon_cam = QIcon(os.path.join(icons_dir, "tm_camera.svg"))
    act_cam = QAction(icon_cam, "Camera", toolbar)
    act_cam.setToolTip("Toggle live DCC Camera Sync with Twinmotion")
    act_cam.setCheckable(True)
    if panel:
        act_cam.toggled.connect(panel.chk_camera_sync.setChecked)
    toolbar.addAction(act_cam)

    # Disconnect Action
    icon_disc = QIcon(os.path.join(icons_dir, "tm_disconnect.svg"))
    act_disc = QAction(icon_disc, "Disconnect", toolbar)
    act_disc.setToolTip("Stop DirectLink Beacon")
    act_disc.triggered.connect(lambda: engine.bridge.stop_endpoint(log_cb=panel._add_log if panel else None))
    toolbar.addAction(act_disc)

    toolbar.setVisible(True)
    toolbar.show()

    if hasattr(app, "restore_toolbar_layout"):
        try:
            app.restore_toolbar_layout()
        except Exception:
            pass

    return toolbar


def setup(app: Any):
    global _GLOBAL_BRIDGE, _GLOBAL_ENGINE, _GLOBAL_PANEL, _GLOBAL_TOOLBAR

    source_name = ENV_CONFIG.get("DIRECTLINK_SOURCE_NAME", "IngeTrazo")
    stream_name = ENV_CONFIG.get("DIRECTLINK_STREAM_NAME", "IngeTrazo LiveSync")

    _GLOBAL_BRIDGE = DirectLinkBridge(source_name=source_name, stream_name=stream_name)
    _GLOBAL_BRIDGE.start_endpoint()

    _GLOBAL_ENGINE = TMSyncEngine(bridge=_GLOBAL_BRIDGE)

    if hasattr(app, "add_panel"):
        _GLOBAL_PANEL = TMSyncDockPanel(app=app, engine=_GLOBAL_ENGINE)
        app.add_panel("Twinmotion LiveSync", _GLOBAL_PANEL)
        TMSyncManager._log(app, "Twinmotion LiveSync panel loaded into side tray.")
    else:
        TMSyncManager._log(app, "Twinmotion LiveSync extension initialized.")

    # Initialize Toolbar
    _GLOBAL_TOOLBAR = setup_toolbar(app, _GLOBAL_ENGINE, _GLOBAL_PANEL)


def teardown(app: Any = None):
    global _GLOBAL_BRIDGE, _GLOBAL_TOOLBAR
    if _GLOBAL_BRIDGE:
        _GLOBAL_BRIDGE.stop_endpoint()
        _GLOBAL_BRIDGE = None

    if _GLOBAL_TOOLBAR:
        window = getattr(app, "window", None)
        if window and hasattr(window, "removeToolBar"):
            window.removeToolBar(_GLOBAL_TOOLBAR)
        _GLOBAL_TOOLBAR = None

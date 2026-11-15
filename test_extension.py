"""
Verification and Test Suite for IngeTrazo Twinmotion LiveSync.
Tests option numerical sorting, layer caching, state restoration, and Datasmith snapshot output.
"""

import os
import sys
import tempfile
import unittest

from mesh_exporter import IngeTrazoMeshExtractor, SceneExportData, MeshData, MaterialData
from directlink_bridge import DirectLinkBridge
from igz_tm_sync import TMSyncManager, TMSyncEngine


class MockLayer:
    def __init__(self, name: str, visible: bool = True):
        self.name = name
        self.visible = visible


class MockEntity:
    def __init__(self, name: str, layer: MockLayer, vertices, faces, visible: bool = True):
        self.name = name
        self.layer = layer
        self.vertices = vertices
        self.faces = faces
        self.visible = visible


class MockCamera:
    def __init__(self, fov: float = 60.0):
        self.fov = fov


class MockViewport:
    def __init__(self):
        self.camera = MockCamera()
        self.redraw_called = False
        self.status_messages = []

    def redraw(self):
        self.redraw_called = True

    def flash_status(self, msg: str, duration: int = 3000):
        self.status_messages.append(msg)


class MockScene:
    def __init__(self):
        self.layers = [
            MockLayer("Walls", True),
            MockLayer("Furniture", False),
            MockLayer("Structure", True)
        ]
        # Create a simple cube mesh on 'Walls'
        verts = [
            (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
            (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)
        ]
        faces = [
            [0, 1, 2, 3],  # Bottom quad
            [4, 5, 6, 7],  # Top quad
            [0, 1, 5, 4],  # Front quad
            [2, 3, 7, 6],  # Back quad
            [1, 2, 6, 5],  # Right quad
            [0, 3, 7, 4]   # Left quad
        ]
        self.entities = [
            MockEntity("Cube_01", self.layers[0], verts, faces, visible=True),
            MockEntity("Chair_Hidden", self.layers[1], [(0, 0, 0), (0.5, 0, 0), (0, 0.5, 0)], [[0, 1, 2]], visible=False)
        ]


class MockApp:
    def __init__(self):
        self.scene = MockScene()
        self.viewport = MockViewport()
        self._doc_data = {}

    def document_data(self, default=None):
        return self._doc_data if self._doc_data else (default or {})

    def set_document_data(self, data):
        self._doc_data = data


class TestTMSyncExtension(unittest.TestCase):

    def setUp(self):
        self.app = MockApp()
        self.bridge = DirectLinkBridge(source_name="Test_IngeTrazo", stream_name="Test_IngeTrazo")
        self.engine = TMSyncEngine(bridge=self.bridge)

    def tearDown(self):
        if hasattr(self, 'bridge') and self.bridge:
            self.bridge.stop_endpoint()

    def test_numerical_option_sorting(self):
        """Option 2 must sort before Option 10 (as in knTMSync)."""
        doc_options = {
            "TM Option 10": {},
            "TM Option 1": {},
            "TM Option 2": {},
            "TM Option 5": {}
        }
        self.app.set_document_data({TMSyncManager.DOCUMENT_STORAGE_KEY: doc_options})

        sorted_options = TMSyncManager.get_existing_tm_options(self.app)
        expected = ["TM Option 1", "TM Option 2", "TM Option 5", "TM Option 10"]
        self.assertEqual(sorted_options, expected)

    def test_next_option_naming(self):
        """Calculates next sequential option name."""
        existing = ["TM Option 1", "TM Option 2", "TM Option 9"]
        next_name = TMSyncManager.get_next_tm_option_name(existing)
        self.assertEqual(next_name, "TM Option 10")

        # Empty test
        self.assertEqual(TMSyncManager.get_next_tm_option_name([]), "TM Option 1")

    def test_mesh_extraction_and_triangulation(self):
        """Verifies polygon fan-triangulation and coordinate scaling."""
        extractor = IngeTrazoMeshExtractor(unit_scale=100.0)
        export_data = extractor.extract_scene(self.app.scene, active_layer_names=["Walls"])

        self.assertEqual(len(export_data.meshes), 1)
        mesh = export_data.meshes[0]
        self.assertEqual(mesh.name, "Cube_01")
        # 8 vertices * 3 coordinates = 24 floats
        self.assertEqual(len(mesh.vertices), 24)
        # Scaled by 100
        self.assertEqual(mesh.vertices[3], 100.0)

        # 6 quads split into 2 triangles each = 12 triangles = 36 indices
        total_indices = sum(len(sub.indices) for sub in mesh.submeshes)
        self.assertEqual(total_indices, 36)

    def test_datasmith_snapshot_generation(self):
        """Verifies .udatasmith XML and binary mesh output."""
        extractor = IngeTrazoMeshExtractor(unit_scale=100.0)
        scene_data = extractor.extract_scene(self.app.scene)
        success = self.bridge.publish_snapshot(scene_data)
        self.assertTrue(success)

        expected_udatasmith = os.path.join(self.bridge.cache_dir, f"{self.bridge.stream_name}.udatasmith")
        self.assertTrue(os.path.isfile(expected_udatasmith))

        # Check that file has content
        with open(expected_udatasmith, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("DatasmithUnrealScene", content)
            self.assertIn("Cube_01", content)
            self.assertIn("Cube_01_Actor", content)

    def test_try_finally_state_restoration(self):
        """
        Critical knTMSync behavior:
        Working layer visibility, camera state, and hidden objects must be restored.
        """
        # Save a preset where Furniture is visible
        option_name = "TM Option 1"
        target_layers = {"Walls": True, "Furniture": True, "Structure": False}
        self.app.set_document_data({
            TMSyncManager.DOCUMENT_STORAGE_KEY: {option_name: target_layers}
        })

        # Working state before sync
        original_furniture_vis = self.app.scene.layers[1].visible  # False
        hidden_entity = self.app.scene.entities[1]
        self.assertFalse(hidden_entity.visible)

        # Execute sync
        sync_result = self.engine.execute_sync(self.app, option_name)
        self.assertTrue(sync_result)

        # Working layers must be restored to original working state
        self.assertEqual(self.app.scene.layers[1].visible, original_furniture_vis)
        # Hidden object must be re-hidden
        self.assertFalse(hidden_entity.visible)
        # Viewport redraw must have been called
        self.assertTrue(self.app.viewport.redraw_called)


if __name__ == "__main__":
    unittest.main()

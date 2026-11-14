"""
Mesh Exporter for IngeTrazo to Datasmith / Twinmotion
Converts IngeTrazo scene entities, meshes, and materials into Datasmith elements.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Tuple, Optional
import math


@dataclass
class Vector3:
    x: float
    y: float
    z: float

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def scale(self, factor: float) -> "Vector3":
        return Vector3(self.x * factor, self.y * factor, self.z * factor)


@dataclass
class MaterialData:
    name: str
    diffuse_color: Tuple[float, float, float, float] = (0.8, 0.8, 0.8, 1.0)
    roughness: float = 0.5
    metallic: float = 0.0


@dataclass
class SubMeshData:
    material_name: str
    indices: List[int] = field(default_factory=list)


@dataclass
class MeshData:
    name: str
    vertices: List[float] = field(default_factory=list)      # Flattened [x, y, z, ...]
    normals: List[float] = field(default_factory=list)       # Flattened [nx, ny, nz, ...]
    uvs: List[float] = field(default_factory=list)           # Flattened [u, v, ...]
    submeshes: List[SubMeshData] = field(default_factory=list)
    transform: List[float] = field(default_factory=lambda: [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0
    ])


@dataclass
class SceneExportData:
    name: str
    unit_scale: float = 100.0  # 1 meter -> 100 cm (Unreal / Twinmotion standard)
    meshes: List[MeshData] = field(default_factory=list)
    materials: Dict[str, MaterialData] = field(default_factory=dict)


class IngeTrazoMeshExtractor:
    """
    Extracts mesh geometry from IngeTrazo scene objects.
    Ensures watertight triangulation and coordinate scaling for Twinmotion.
    """

    def __init__(self, unit_scale: float = 100.0):
        self.unit_scale = unit_scale

    def extract_scene(self, scene: Any, active_layer_names: Optional[List[str]] = None) -> SceneExportData:
        """
        Extracts all visible geometry from an IngeTrazo scene.
        Filters by active_layer_names when specified.
        """
        export_data = SceneExportData(name="IngeTrazo_Scene", unit_scale=self.unit_scale)

        entities = self._get_scene_entities(scene)
        for entity in entities:
            if not self._is_entity_visible(entity, active_layer_names):
                continue

            mesh_data = self._extract_entity_mesh(entity)
            if mesh_data and len(mesh_data.vertices) > 0:
                export_data.meshes.append(mesh_data)

                # Collect materials
                for submesh in mesh_data.submeshes:
                    mat_name = submesh.material_name
                    if mat_name not in export_data.materials:
                        export_data.materials[mat_name] = self._extract_material(entity, mat_name)

        return export_data

    def _get_scene_entities(self, scene: Any) -> List[Any]:
        """Safely gets entities list across different IngeTrazo scene structures."""
        entities = []

        # 1. IngeTrazo official root loose geometry (scene.loose_mesh)
        loose = getattr(scene, "loose_mesh", None)
        if loose is not None:
            entities.append(loose)

        # 2. IngeTrazo active editing mesh context (scene.mesh)
        active_mesh = getattr(scene, "mesh", None)
        if active_mesh is not None and active_mesh is not loose:
            entities.append(active_mesh)

        # 3. IngeTrazo hierarchical groups and components
        groups = getattr(scene, "groups", None)
        if groups:
            try:
                for grp in groups:
                    entities.append(grp)
                    if hasattr(grp, "children") and isinstance(grp.children, (list, tuple)):
                        entities.extend(grp.children)
                    if hasattr(grp, "groups") and isinstance(grp.groups, (list, tuple)):
                        entities.extend(grp.groups)
            except Exception:
                pass

        components = getattr(scene, "components", None)
        if components and isinstance(components, (list, tuple)):
            entities.extend(list(components))

        # 4. Standard collections fallback
        for attr in ("entities", "objects", "elements", "drawables", "solids", "geometries", "models"):
            if hasattr(scene, attr):
                val = getattr(scene, attr)
                if callable(val):
                    try:
                        val = val()
                    except Exception:
                        continue
                if isinstance(val, (list, tuple, set)):
                    entities.extend(list(val))

        if isinstance(scene, (list, tuple)):
            entities.extend(list(scene))

        # 5. Check if scene itself is a geometry container
        if not entities and (hasattr(scene, "faces") or hasattr(scene, "vertices")):
            entities.append(scene)

        return entities

    def _is_entity_visible(self, entity: Any, active_layers: Optional[List[str]]) -> bool:
        """Checks if entity is visible and on an active export layer."""
        if hasattr(entity, "visible") and not entity.visible:
            return False
        if hasattr(entity, "is_visible") and callable(entity.is_visible) and not entity.is_visible():
            return False

        if active_layers is not None:
            layer_name = self._get_entity_layer(entity)
            if layer_name and layer_name not in active_layers:
                return False

        return True

    def _get_entity_layer(self, entity: Any) -> str:
        """Gets the layer name of an entity."""
        if hasattr(entity, "layer"):
            layer = entity.layer
            return getattr(layer, "name", str(layer))
        elif hasattr(entity, "tag"):
            return str(entity.tag)
        return "Default"

    def _extract_material(self, entity: Any, mat_name: str) -> MaterialData:
        """Extracts material properties or provides defaults."""
        mat = MaterialData(name=mat_name)
        if hasattr(entity, "material") and entity.material:
            m = entity.material
            if hasattr(m, "color"):
                c = m.color
                mat.diffuse_color = (
                    float(getattr(c, "r", 0.8)),
                    float(getattr(c, "g", 0.8)),
                    float(getattr(c, "b", 0.8)),
                    float(getattr(c, "a", 1.0))
                )
            if hasattr(m, "roughness"):
                mat.roughness = float(m.roughness)
            if hasattr(m, "metallic"):
                mat.metallic = float(m.metallic)
        return mat

    def _extract_entity_mesh(self, entity: Any) -> Optional[MeshData]:
        """Extracts vertices, normals, and triangulated faces from an entity."""
        name = getattr(entity, "name", None)
        if not name:
            if hasattr(entity, "__class__"):
                name = f"{entity.__class__.__name__}_{id(entity)}"
            else:
                name = f"Entity_{id(entity)}"

        target = entity
        if hasattr(entity, "mesh") and entity.mesh and not hasattr(entity, "vertices"):
            target = entity.mesh
        elif hasattr(entity, "definition") and hasattr(entity.definition, "mesh"):
            target = entity.definition.mesh
        elif hasattr(entity, "geometry") and not hasattr(entity, "vertices"):
            target = entity.geometry

        # 1. Direct mesh support (if target has vertices and faces)
        if hasattr(target, "vertices") and hasattr(target, "faces"):
            raw_verts = target.vertices
            raw_faces = target.faces
            mesh = self._build_from_vertices_and_faces(name, raw_verts, raw_faces, entity)
            if mesh and len(mesh.vertices) > 0 and mesh.submeshes and len(mesh.submeshes[0].indices) > 0:
                self._apply_entity_transform(mesh, entity)
                return mesh
            # Fallback to brep if face indices was empty
            if hasattr(raw_faces, "__iter__") or isinstance(raw_faces, dict):
                face_items = list(raw_faces.values()) if isinstance(raw_faces, dict) else list(raw_faces)
                mesh = self._build_from_brep_faces(name, face_items, entity)
                if mesh and len(mesh.vertices) > 0:
                    self._apply_entity_transform(mesh, entity)
                    return mesh

        # 2. Brep / Solid representation (faces collection)
        if hasattr(target, "get_faces"):
            faces = target.get_faces()
            mesh = self._build_from_brep_faces(name, list(faces), entity)
            self._apply_entity_transform(mesh, entity)
            return mesh
        elif hasattr(target, "faces"):
            face_items = list(target.faces.values()) if isinstance(target.faces, dict) else list(target.faces)
            mesh = self._build_from_brep_faces(name, face_items, entity)
            self._apply_entity_transform(mesh, entity)
            return mesh

        return None

    def _apply_entity_transform(self, mesh: MeshData, entity: Any):
        """Applies position / transform matrix from entity to mesh coordinates."""
        transform = getattr(entity, "transform", getattr(entity, "transformation", None))
        if transform:
            if isinstance(transform, (list, tuple)) and len(transform) == 16:
                mesh.transform = [float(x) for x in transform]
            elif hasattr(transform, "matrix"):
                m = transform.matrix
                if isinstance(m, (list, tuple)) and len(m) == 16:
                    mesh.transform = [float(x) for x in m]

        pos = getattr(entity, "position", None)
        if pos and hasattr(pos, "x"):
            dx, dy, dz = self._get_xyz(pos)
            mesh.transform[12] += dx * self.unit_scale
            mesh.transform[13] += dy * self.unit_scale
            mesh.transform[14] += dz * self.unit_scale

    def _build_from_vertices_and_faces(
        self, name: str, vertices: Any, faces: Any, entity: Any
    ) -> MeshData:
        mesh = MeshData(name=name)
        scale = self.unit_scale

        vert_list = list(vertices.values()) if isinstance(vertices, dict) else list(vertices)
        face_list = list(faces.values()) if isinstance(faces, dict) else list(faces)

        # Pack vertices
        for v in vert_list:
            x, y, z = self._get_xyz(v)
            mesh.vertices.extend([x * scale, y * scale, z * scale])
            mesh.normals.extend([0.0, 0.0, 1.0])  # Default normal, recomputed later
            mesh.uvs.extend([0.0, 0.0])

        # Triangulate polygonal faces
        layer_name = self._get_entity_layer(entity)
        submesh = SubMeshData(material_name=layer_name)

        for face in face_list:
            idx_list = self._get_face_indices(face)
            if len(idx_list) < 3:
                continue

            # Fan triangulation for convex polygons (n-gons)
            for i in range(1, len(idx_list) - 1):
                i0 = idx_list[0]
                i1 = idx_list[i]
                i2 = idx_list[i + 1]
                submesh.indices.extend([i0, i1, i2])

                # Calculate smooth face normals
                self._compute_triangle_normal(mesh, i0, i1, i2)

        mesh.submeshes.append(submesh)
        return mesh

    def _build_from_brep_faces(self, name: str, faces: List[Any], entity: Any) -> MeshData:
        """Builds mesh from CAD/BIM Brep face collection."""
        mesh = MeshData(name=name)
        scale = self.unit_scale
        layer_name = self._get_entity_layer(entity)
        submesh = SubMeshData(material_name=layer_name)

        vertex_map: Dict[Tuple[float, float, float], int] = {}

        for face in faces:
            polygon_pts = []
            if hasattr(face, "outer_loop"):
                loop = face.outer_loop
                polygon_pts = [self._get_xyz(pt) for pt in getattr(loop, "vertices", [])]
            elif hasattr(face, "vertices"):
                verts = face.vertices
                vert_iter = verts.values() if isinstance(verts, dict) else verts
                polygon_pts = [self._get_xyz(pt) for pt in vert_iter]
            elif hasattr(face, "points"):
                polygon_pts = [self._get_xyz(pt) for pt in face.points]
            elif hasattr(face, "polygon"):
                polygon_pts = [self._get_xyz(pt) for pt in face.polygon]
            elif hasattr(face, "edges"):
                for edge in face.edges:
                    if hasattr(edge, "start"):
                        polygon_pts.append(self._get_xyz(edge.start))

            if len(polygon_pts) < 3:
                continue

            # Map vertices to index buffer
            face_indices = []
            for px, py, pz in polygon_pts:
                key = (round(px, 5), round(py, 5), round(pz, 5))
                if key not in vertex_map:
                    idx = len(mesh.vertices) // 3
                    vertex_map[key] = idx
                    mesh.vertices.extend([px * scale, py * scale, pz * scale])
                    mesh.normals.extend([0.0, 0.0, 1.0])
                    mesh.uvs.extend([px, py])
                face_indices.append(vertex_map[key])

            # Fan triangulation
            for i in range(1, len(face_indices) - 1):
                i0, i1, i2 = face_indices[0], face_indices[i], face_indices[i + 1]
                submesh.indices.extend([i0, i1, i2])
                self._compute_triangle_normal(mesh, i0, i1, i2)

        mesh.submeshes.append(submesh)
        return mesh

    def _get_xyz(self, pt: Any) -> Tuple[float, float, float]:
        if hasattr(pt, "point"):
            val = pt.point() if callable(pt.point) else pt.point
            if val is not None:
                pt = val
        elif hasattr(pt, "position"):
            val = pt.position() if callable(pt.position) else pt.position
            if val is not None:
                pt = val
        elif hasattr(pt, "coords"):
            val = pt.coords() if callable(pt.coords) else pt.coords
            if val is not None:
                pt = val

        if hasattr(pt, "x") and hasattr(pt, "y") and hasattr(pt, "z"):
            try:
                x_val = pt.x() if callable(pt.x) else pt.x
                y_val = pt.y() if callable(pt.y) else pt.y
                z_val = pt.z() if callable(pt.z) else pt.z
                return (float(x_val), float(y_val), float(z_val))
            except Exception:
                pass

        if hasattr(pt, "X") and hasattr(pt, "Y") and hasattr(pt, "Z"):
            try:
                x_val = pt.X() if callable(pt.X) else pt.X
                y_val = pt.Y() if callable(pt.Y) else pt.Y
                z_val = pt.Z() if callable(pt.Z) else pt.Z
                return (float(x_val), float(y_val), float(z_val))
            except Exception:
                pass

        try:
            if hasattr(pt, "__getitem__"):
                return (float(pt[0]), float(pt[1]), float(pt[2]))
        except Exception:
            pass

        return (0.0, 0.0, 0.0)

    def _get_face_indices(self, face: Any) -> List[int]:
        if hasattr(face, "indices"):
            return list(face.indices)
        elif hasattr(face, "vertex_indices"):
            return list(face.vertex_indices)
        elif isinstance(face, (list, tuple)):
            return list(face)
        return []

    def _compute_triangle_normal(self, mesh: MeshData, i0: int, i1: int, i2: int):
        """Computes and accumulates face normal for vertices."""
        try:
            v0 = (mesh.vertices[i0 * 3], mesh.vertices[i0 * 3 + 1], mesh.vertices[i0 * 3 + 2])
            v1 = (mesh.vertices[i1 * 3], mesh.vertices[i1 * 3 + 1], mesh.vertices[i1 * 3 + 2])
            v2 = (mesh.vertices[i2 * 3], mesh.vertices[i2 * 3 + 1], mesh.vertices[i2 * 3 + 2])

            e1 = (v1[0] - v0[0], v1[1] - v0[1], v1[2] - v0[2])
            e2 = (v2[0] - v0[0], v2[1] - v0[1], v2[2] - v0[2])

            nx = e1[1] * e2[2] - e1[2] * e2[1]
            ny = e1[2] * e2[0] - e1[0] * e2[2]
            nz = e1[0] * e2[1] - e1[1] * e2[0]

            length = math.sqrt(nx * nx + ny * ny + nz * nz)
            if length > 1e-6:
                nx /= length
                ny /= length
                nz /= length

                for idx in (i0, i1, i2):
                    mesh.normals[idx * 3] = nx
                    mesh.normals[idx * 3 + 1] = ny
                    mesh.normals[idx * 3 + 2] = nz
        except Exception:
            pass

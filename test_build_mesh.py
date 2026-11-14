"""
Test creating a FDatasmithFacadeMesh, MeshElement, ActorMesh, and exporting to scene
"""
import ctypes
import os

datasmith_dir = r"C:\ProgramData\McNeel\Rhinoceros\7.0\Plug-ins\Datasmith Rhino Exporter (d1fdc795-b334-4933-b680-088119cdc6bb)"
os.add_dll_directory(datasmith_dir)
dll = ctypes.CDLL(os.path.join(datasmith_dir, "DatasmithFacadeCSharp.dll"))

# 1. Inspect ExportDatasmithMesh SWIG variants
print("Testing ExportDatasmithMesh and Mesh API...")

# Mesh
new_mesh = dll.CSharp_new_FDatasmithFacadeMesh
new_mesh.restype = ctypes.c_void_p
new_mesh.argtypes = []
mesh_ptr = new_mesh()
print(f"Mesh ptr: {hex(mesh_ptr)}")

set_name = dll.CSharp_FDatasmithFacadeMesh_SetName
set_name.restype = None
set_name.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
set_name(mesh_ptr, u"TestBoxMesh")

set_vert_cnt = dll.CSharp_FDatasmithFacadeMesh_SetVerticesCount
set_vert_cnt.restype = None
set_vert_cnt.argtypes = [ctypes.c_void_p, ctypes.c_int]
set_vert_cnt(mesh_ptr, 4)

set_vert = dll.CSharp_FDatasmithFacadeMesh_SetVertex
set_vert.restype = None
set_vert.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_float, ctypes.c_float, ctypes.c_float]
# Quad: 4 vertices (100cm box)
set_vert(mesh_ptr, 0, 0.0, 0.0, 0.0)
set_vert(mesh_ptr, 1, 100.0, 0.0, 0.0)
set_vert(mesh_ptr, 2, 100.0, 100.0, 0.0)
set_vert(mesh_ptr, 3, 0.0, 100.0, 0.0)

set_faces_cnt = dll.CSharp_FDatasmithFacadeMesh_SetFacesCount
set_faces_cnt.restype = None
set_faces_cnt.argtypes = [ctypes.c_void_p, ctypes.c_int]
set_faces_cnt(mesh_ptr, 2)

# SetFace: (mesh_ptr, face_index, v0, v1, v2, mat_id)
set_face = dll.CSharp_FDatasmithFacadeMesh_SetFace__SWIG_0
set_face.restype = None
set_face.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p]
try:
    set_face(mesh_ptr, 0, 0, 1, 2, u"DefaultMaterial")
    set_face(mesh_ptr, 1, 0, 2, 3, u"DefaultMaterial")
    print("SetFace SWIG_0 succeeded with wchar_t* mat")
except Exception as e:
    print(f"SetFace SWIG_0 failed: {e}")
    # try int materialId: SWIG_1
    set_face1 = dll.CSharp_FDatasmithFacadeMesh_SetFace__SWIG_1
    set_face1.restype = None
    set_face1.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    set_face1(mesh_ptr, 0, 0, 1, 2, 0)
    set_face1(mesh_ptr, 1, 0, 2, 3, 0)
    print("SetFace SWIG_1 succeeded with int mat_id")

# MeshElement
new_mesh_elem = dll.CSharp_new_FDatasmithFacadeMeshElement
new_mesh_elem.restype = ctypes.c_void_p
new_mesh_elem.argtypes = [ctypes.c_wchar_p]
mesh_elem_ptr = new_mesh_elem(u"TestBoxMesh")
print(f"MeshElement ptr: {hex(mesh_elem_ptr)}")

# Scene
new_scene = dll.CSharp_new_FDatasmithFacadeScene
new_scene.restype = ctypes.c_void_p
new_scene.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p]
scene_ptr = new_scene(u"IngeTrazo LiveSync", u"IngeTrazo", u"1.0", u"1.0")

# ExportDatasmithMesh
# Check SWIG variants
exp_mesh0 = dll.CSharp_FDatasmithFacadeScene_ExportDatasmithMesh__SWIG_0
exp_mesh0.restype = ctypes.c_bool
# What are argtypes? Let's check: (scene_ptr, mesh_elem_ptr, mesh_ptr) or (scene_ptr, mesh_elem_ptr, mesh_ptr, bool)
print("Testing ExportDatasmithMesh call...")
try:
    exp_mesh0.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    res = exp_mesh0(scene_ptr, mesh_elem_ptr, mesh_ptr)
    print(f"ExportDatasmithMesh__SWIG_0(scene, elem, mesh) -> {res}")
except Exception as e:
    print(f"ExportDatasmithMesh__SWIG_0 failed: {e}")

# AddMesh to scene
add_mesh = dll.CSharp_FDatasmithFacadeScene_AddMesh
add_mesh.restype = None
add_mesh.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
add_mesh(scene_ptr, mesh_elem_ptr)
print("Added MeshElement to Scene")

# ActorMesh
new_actor = dll.CSharp_new_FDatasmithFacadeActorMesh
new_actor.restype = ctypes.c_void_p
new_actor.argtypes = [ctypes.c_wchar_p]
actor_ptr = new_actor(u"TestBoxActor")
print(f"ActorMesh ptr: {hex(actor_ptr)}")

set_mesh = dll.CSharp_FDatasmithFacadeActorMesh_SetMesh
set_mesh.restype = None
set_mesh.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
set_mesh(actor_ptr, u"TestBoxMesh")
print("Set actor mesh reference to 'TestBoxMesh'")

# AddActor to scene
add_actor = dll.CSharp_FDatasmithFacadeScene_AddActor
add_actor.restype = None
add_actor.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
add_actor(scene_ptr, actor_ptr)
print("Added Actor to Scene")

# PreExport
pre_export = dll.CSharp_FDatasmithFacadeScene_PreExport
pre_export.restype = None
pre_export.argtypes = [ctypes.c_void_p]
pre_export(scene_ptr)
print("Scene PreExport completed successfully!")

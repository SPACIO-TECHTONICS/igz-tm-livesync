"""
Test full mesh synchronization to Twinmotion
"""
import ctypes
import os
import struct

datasmith_dir = r"C:\ProgramData\McNeel\Rhinoceros\7.0\Plug-ins\Datasmith Rhino Exporter (d1fdc795-b334-4933-b680-088119cdc6bb)"
os.add_dll_directory(datasmith_dir)
dll = ctypes.CDLL(os.path.join(datasmith_dir, "DatasmithFacadeCSharp.dll"))

# 1. Initialize Options
class FInitOptions(ctypes.Structure):
    _fields_ = [
        ("bLogNone", ctypes.c_bool),
        ("bSaveToUserDir", ctypes.c_bool),
        ("bEnableMessaging", ctypes.c_bool),
        ("bEnableUI", ctypes.c_bool),
        ("padding", ctypes.c_char * 60)
    ]

opts = FInitOptions()
opts.bLogNone = False
opts.bSaveToUserDir = False
opts.bEnableMessaging = True
opts.bEnableUI = False

init_opts = getattr(dll, "?Initialize@FDatasmithExporterManager@@SA_NAEBUFInitOptions@1@@Z")
init_opts.restype = ctypes.c_bool
init_opts.argtypes = [ctypes.POINTER(FInitOptions)]
init_opts(ctypes.byref(opts))

# 2. DirectLink Init
cache_dir = r"C:\Users\kesha\AppData\Local\Temp\IngeTrazo_DirectLink"
os.makedirs(cache_dir, exist_ok=True)

init_dl = getattr(dll, "?Init@FDatasmithFacadeDirectLink@@SA_N_NPEB_W@Z")
init_dl.restype = ctypes.c_bool
init_dl.argtypes = [ctypes.c_bool, ctypes.c_wchar_p]
init_dl(True, cache_dir)

# 3. Create Scene
new_scene = dll.CSharp_new_FDatasmithFacadeScene
new_scene.restype = ctypes.c_void_p
new_scene.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p]
scene_ptr = new_scene(u"IngeTrazo LiveSync", u"IngeTrazo", u"1.0", u"1.0")

set_out = dll.CSharp_FDatasmithFacadeScene_SetOutputPath
set_out.restype = None
set_out.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
set_out(scene_ptr, cache_dir)

# 4. Create DirectLink
new_dl = dll.CSharp_new_FDatasmithFacadeDirectLink
new_dl.restype = ctypes.c_void_p
new_dl.argtypes = []
dl_ptr = new_dl()

init_scene = dll.CSharp_FDatasmithFacadeDirectLink_InitializeForScene
init_scene.restype = ctypes.c_bool
init_scene.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
init_scene(dl_ptr, scene_ptr)

# 5. Build a 3D Cube Mesh (8 vertices, 12 triangles)
new_mesh = dll.CSharp_new_FDatasmithFacadeMesh
new_mesh.restype = ctypes.c_void_p
new_mesh.argtypes = []
mesh_ptr = new_mesh()

set_name = dll.CSharp_FDatasmithFacadeMesh_SetName
set_name.restype = None
set_name.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
set_name(mesh_ptr, u"IngeTrazo_Cube")

# 8 vertices for a 100x100x100 cm cube
cube_verts = [
    (-50.0, -50.0, 0.0),   (50.0, -50.0, 0.0),   (50.0, 50.0, 0.0),   (-50.0, 50.0, 0.0),
    (-50.0, -50.0, 100.0), (50.0, -50.0, 100.0), (50.0, 50.0, 100.0), (-50.0, 50.0, 100.0)
]
set_vert_cnt = dll.CSharp_FDatasmithFacadeMesh_SetVerticesCount
set_vert_cnt.restype = None
set_vert_cnt.argtypes = [ctypes.c_void_p, ctypes.c_int]
set_vert_cnt(mesh_ptr, len(cube_verts))

set_vert = dll.CSharp_FDatasmithFacadeMesh_SetVertex
set_vert.restype = None
set_vert.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_float, ctypes.c_float, ctypes.c_float]
for i, (x, y, z) in enumerate(cube_verts):
    set_vert(mesh_ptr, i, x, y, z)

# 12 triangles (6 faces * 2 triangles)
cube_tris = [
    # Bottom
    (0, 2, 1), (0, 3, 2),
    # Top
    (4, 5, 6), (4, 6, 7),
    # Front
    (0, 1, 5), (0, 5, 4),
    # Right
    (1, 2, 6), (1, 6, 5),
    # Back
    (2, 3, 7), (2, 7, 6),
    # Left
    (3, 0, 4), (3, 4, 7)
]
set_faces_cnt = dll.CSharp_FDatasmithFacadeMesh_SetFacesCount
set_faces_cnt.restype = None
set_faces_cnt.argtypes = [ctypes.c_void_p, ctypes.c_int]
set_faces_cnt(mesh_ptr, len(cube_tris))

set_face = dll.CSharp_FDatasmithFacadeMesh_SetFace__SWIG_1
set_face.restype = None
set_face.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
for i, (v0, v1, v2) in enumerate(cube_tris):
    set_face(mesh_ptr, i, v0, v1, v2)

# Export mesh binary
exp_mesh = dll.CSharp_FDatasmithFacadeScene_ExportDatasmithMesh__SWIG_1
exp_mesh.restype = ctypes.c_void_p
exp_mesh.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
mesh_elem_ptr = exp_mesh(scene_ptr, mesh_ptr)
print(f"Mesh exported: {hex(mesh_elem_ptr)}")

# Add to scene
add_mesh = dll.CSharp_FDatasmithFacadeScene_AddMesh
add_mesh.restype = None
add_mesh.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
add_mesh(scene_ptr, mesh_elem_ptr)

# Create Actor
new_actor = dll.CSharp_new_FDatasmithFacadeActorMesh
new_actor.restype = ctypes.c_void_p
new_actor.argtypes = [ctypes.c_wchar_p]
actor_ptr = new_actor(u"IngeTrazo_Cube_Actor")

set_mesh = dll.CSharp_FDatasmithFacadeActorMesh_SetMesh
set_mesh.restype = None
set_mesh.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
set_mesh(actor_ptr, u"IngeTrazo_Cube")

add_actor = dll.CSharp_FDatasmithFacadeScene_AddActor
add_actor.restype = None
add_actor.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
add_actor(scene_ptr, actor_ptr)
print("Actor added to scene!")

# PreExport & UpdateScene
pre_export = dll.CSharp_FDatasmithFacadeScene_PreExport
pre_export.restype = None
pre_export.argtypes = [ctypes.c_void_p]
pre_export(scene_ptr)
print("PreExport done!")

update_scene = dll.CSharp_FDatasmithFacadeDirectLink_UpdateScene
update_scene.restype = ctypes.c_bool
update_scene.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
synced = update_scene(dl_ptr, scene_ptr)
print(f"UpdateScene -> {synced}")
print("LiveSync snapshot with cube geometry transmitted to Twinmotion!")

# Keep process alive for 10 seconds to allow Twinmotion to fetch the snapshot
import time
print("Keeping DirectLink active for 10 seconds...")
time.sleep(10.0)
print("Test completed.")

"""
Find exact function call causing the error
"""
import ctypes
import os

datasmith_dir = r"C:\ProgramData\McNeel\Rhinoceros\7.0\Plug-ins\Datasmith Rhino Exporter (d1fdc795-b334-4933-b680-088119cdc6bb)"
os.add_dll_directory(datasmith_dir)
dll = ctypes.CDLL(os.path.join(datasmith_dir, "DatasmithFacadeCSharp.dll"))

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

cache_dir = r"C:\Users\kesha\AppData\Local\Temp\IngeTrazo_DirectLink"
os.makedirs(cache_dir, exist_ok=True)

new_scene = dll.CSharp_new_FDatasmithFacadeScene
new_scene.restype = ctypes.c_void_p
new_scene.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p]
scene_ptr = new_scene(u"IngeTrazo LiveSync", u"IngeTrazo", u"1.0", u"1.0")

set_out = dll.CSharp_FDatasmithFacadeScene_SetOutputPath
set_out.restype = None
set_out.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p]
set_out(scene_ptr, cache_dir)

new_mesh = dll.CSharp_new_FDatasmithFacadeMesh
new_mesh.restype = ctypes.c_void_p
new_mesh.argtypes = []
mesh_ptr = new_mesh()

print("1. Calling SetVerticesCount...", flush=True)
set_vert_cnt = dll.CSharp_FDatasmithFacadeMesh_SetVerticesCount
set_vert_cnt.restype = None
set_vert_cnt.argtypes = [ctypes.c_void_p, ctypes.c_int]
set_vert_cnt(mesh_ptr, 4)

print("2. Calling SetVertex...", flush=True)
set_vert = dll.CSharp_FDatasmithFacadeMesh_SetVertex
set_vert.restype = None
set_vert.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_float, ctypes.c_float, ctypes.c_float]
set_vert(mesh_ptr, 0, 0.0, 0.0, 0.0)

print("3. Calling SetFacesCount...", flush=True)
set_faces_cnt = dll.CSharp_FDatasmithFacadeMesh_SetFacesCount
set_faces_cnt.restype = None
set_faces_cnt.argtypes = [ctypes.c_void_p, ctypes.c_int]
set_faces_cnt(mesh_ptr, 2)

print("4. Calling SetFace SWIG_1...", flush=True)
set_face1 = dll.CSharp_FDatasmithFacadeMesh_SetFace__SWIG_1
set_face1.restype = None
set_face1.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
set_face1(mesh_ptr, 0, 0, 1, 2)

print("5. Calling new_mesh_elem...", flush=True)
new_mesh_elem = dll.CSharp_new_FDatasmithFacadeMeshElement
new_mesh_elem.restype = ctypes.c_void_p
new_mesh_elem.argtypes = [ctypes.c_wchar_p]
mesh_elem_ptr = new_mesh_elem(u"TestBoxMesh")

print("6. Calling ExportDatasmithMesh...", flush=True)
exp_mesh = dll.CSharp_FDatasmithFacadeScene_ExportDatasmithMesh__SWIG_0
exp_mesh.restype = ctypes.c_bool
exp_mesh.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
ok = exp_mesh(scene_ptr, mesh_elem_ptr, mesh_ptr)
print(f"ExportDatasmithMesh result: {ok}")

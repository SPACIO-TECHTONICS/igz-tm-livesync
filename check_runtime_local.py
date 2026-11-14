"""
Check runtime files, hashes, and compiler for IngeTrazo Twinmotion Sync
"""
import hashlib
import os
from pathlib import Path

HASHES = {
    'DatasmithFacadeCSharp.dll': 'eb3e4881629244bbc3a5cb1062aa579d79f68ebb682b5140a274c7c0d1d6fc08',
    'DatasmithRhino6.rhp': '77e2073dc7bd792896f976562f97f125dd1289231338b20ef5bd8d2b6795cd1d',
    'tbbmalloc.dll': '87abcd8f7e31003ab049962a97eb645310be1ccab7ba148c46b2cde5262027bf',
}
MSI_HASH = '7f0e3039e9c8a772b20654342854d497c16799a92077ba2a9df0e9076f1b1927'

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

print("--- 1. Checking C# Compiler ---")
compiler = Path(os.environ.get('WINDIR', 'C:\\Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
print(f"Compiler exists: {compiler.is_file()} ({compiler})")

print("\n--- 2. Checking C:\\DatasmithRuntime ---")
ds_runtime = Path('C:/DatasmithRuntime')
if ds_runtime.is_dir():
    print(f"Directory exists: {ds_runtime}")
    for item in ds_runtime.iterdir():
        if item.is_file():
            digest = sha256_file(item)
            match = HASHES.get(item.name) == digest
            print(f"  {item.name}: {digest} (Match: {match})")
else:
    print(f"Directory does not exist: {ds_runtime}")

print("\n--- 3. Checking Installed Rhino Plugins ---")
rhino_plugin_dir = Path(r"C:\ProgramData\McNeel\Rhinoceros\7.0\Plug-ins\Datasmith Rhino Exporter (d1fdc795-b334-4933-b680-088119cdc6bb)")
if rhino_plugin_dir.is_dir():
    print(f"Directory exists: {rhino_plugin_dir}")
    for item in rhino_plugin_dir.iterdir():
        if item.is_file():
            digest = sha256_file(item)
            match = HASHES.get(item.name) == digest
            print(f"  {item.name}: {digest} (Match: {match})")
else:
    print(f"Directory does not exist: {rhino_plugin_dir}")

print("\n--- 4. Checking Downloads / Temp for Datasmith MSI ---")
search_dirs = [
    Path.home() / 'Downloads',
    Path('C:/DatasmithRuntime'),
    Path(os.environ.get('TEMP', 'C:/Users/kesha/AppData/Local/Temp'))
]
found_msi = []
for sdir in search_dirs:
    if sdir.is_dir():
        for msi in sdir.glob("*Datasmith*.msi"):
            digest = sha256_file(msi)
            match = digest == MSI_HASH
            print(f"Found MSI: {msi}")
            print(f"  Size: {msi.stat().st_size} bytes")
            print(f"  SHA256: {digest} (Expected match: {match})")
            found_msi.append(msi)

if not found_msi:
    print("No Datasmith MSI found in Downloads or Temp.")

"""
Extract official Datasmith runtime files from MSI via MsiRecordReadStream and extrac32
"""
import ctypes
from ctypes import wintypes
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys

MSI_PATH = Path(os.environ.get("TEMP", "C:/Temp")) / "Datasmith_Extract" / "UnrealDatasmithRhinoExporter_5_8_400.msi"
TARGET_DIR = Path("C:/DatasmithRuntime")

EXPECTED_HASHES = {
    'DatasmithFacadeCSharp.dll': 'eb3e4881629244bbc3a5cb1062aa579d79f68ebb682b5140a274c7c0d1d6fc08',
    'DatasmithRhino6.rhp': '77e2073dc7bd792896f976562f97f125dd1289231338b20ef5bd8d2b6795cd1d',
    'tbbmalloc.dll': '87abcd8f7e31003ab049962a97eb645310be1ccab7ba148c46b2cde5262027bf',
}

# Mapping identified from File table in MSI
FILE_MAP = {
    'FacadeDLL6.dll': 'DatasmithFacadeCSharp.dll',
    'DatasmithRhino6.rhp': 'DatasmithRhino6.rhp',
    'TbbDLL6': 'tbbmalloc.dll',
}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def extract_cab_from_msi(msi_file: Path, stream_name: str, out_cab_file: Path):
    msi = ctypes.windll.msi
    
    MSIDBOPEN_READONLY = 0
    hDb = wintypes.HANDLE()
    res = msi.MsiOpenDatabaseW(str(msi_file), MSIDBOPEN_READONLY, ctypes.byref(hDb))
    if res != 0:
        raise RuntimeError(f"MsiOpenDatabaseW failed with error code: {res}")
        
    try:
        hView = wintypes.HANDLE()
        query = f"SELECT `Data` FROM `_Streams` WHERE `Name` = '{stream_name}'"
        res = msi.MsiDatabaseOpenViewW(hDb, query, ctypes.byref(hView))
        if res != 0:
            raise RuntimeError(f"MsiDatabaseOpenViewW failed: {res}")
            
        try:
            res = msi.MsiViewExecute(hView, 0)
            if res != 0:
                raise RuntimeError(f"MsiViewExecute failed: {res}")
                
            hRecord = wintypes.HANDLE()
            res = msi.MsiViewFetch(hView, ctypes.byref(hRecord))
            if res != 0:
                raise RuntimeError(f"MsiViewFetch failed to find stream '{stream_name}': {res}")
                
            try:
                buf_size = 65536
                buf = ctypes.create_string_buffer(buf_size)
                bytes_read = wintypes.DWORD(buf_size)
                
                out_cab_file.parent.mkdir(parents=True, exist_ok=True)
                total_bytes = 0
                with open(out_cab_file, 'wb') as f_out:
                    while True:
                        bytes_read.value = buf_size
                        res = msi.MsiRecordReadStream(hRecord, 1, buf, ctypes.byref(bytes_read))
                        if res != 0:
                            raise RuntimeError(f"MsiRecordReadStream failed: {res}")
                        if bytes_read.value == 0:
                            break
                        f_out.write(buf.raw[:bytes_read.value])
                        total_bytes += bytes_read.value
                        
                print(f"Extracted '{stream_name}' ({total_bytes} bytes) to {out_cab_file}")
            finally:
                msi.MsiCloseHandle(hRecord)
        finally:
            msi.MsiCloseHandle(hView)
    finally:
        msi.MsiCloseHandle(hDb)

def main():
    print(f"MSI path: {MSI_PATH}")
    if not MSI_PATH.is_file():
        raise FileNotFoundError(f"MSI not found at {MSI_PATH}")
        
    work_dir = MSI_PATH.parent / "extracted_runtime"
    work_dir.mkdir(parents=True, exist_ok=True)
    
    cab_path = work_dir / "DatasmithRhinoExporter.cab"
    
    # 1. Extract CAB stream from MSI
    print("--- 1. Extracting CAB stream from MSI via Windows Msi.dll ---")
    extract_cab_from_msi(MSI_PATH, "DatasmithRhinoExporter.cab", cab_path)
    
    # 2. Extract CAB using Windows extrac32.exe
    cab_out = work_dir / "cab_files"
    if cab_out.exists():
        shutil.rmtree(cab_out, ignore_errors=True)
    cab_out.mkdir(parents=True, exist_ok=True)
    
    print(f"\n--- 2. Unpacking CAB to {cab_out} via extrac32.exe ---")
    ext_cmd = f'extrac32.exe /Y /E /L "{cab_out.resolve()}" "{cab_path.resolve()}"'
    res = subprocess.run(ext_cmd, shell=True, capture_output=True, text=True)
    print(f"extrac32 exit code: {res.returncode}")
    
    # 3. Locate and verify target files
    print("\n--- 3. Verifying and mapping extracted files ---")
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    
    verified_files = {}
    for cab_key, final_name in FILE_MAP.items():
        src = cab_out / cab_key
        if not src.is_file():
            # Search case-insensitive or in subdirectories
            for p in cab_out.rglob("*"):
                if p.name.lower() == cab_key.lower():
                    src = p
                    break
                    
        if not src.is_file():
            print(f"ERROR: Missing file for {cab_key} (expected {final_name})")
            continue
            
        digest = sha256_file(src)
        expected_digest = EXPECTED_HASHES[final_name]
        matches = digest == expected_digest
        print(f"File '{cab_key}' -> '{final_name}':")
        print(f"  SHA256: {digest}")
        print(f"  Match:  {matches}")
        
        if not matches:
            raise ValueError(f"Hash mismatch for {final_name}: got {digest}, expected {expected_digest}")
            
        dst = TARGET_DIR / final_name
        shutil.copy2(src, dst)
        print(f"  Installed -> {dst}")
        verified_files[final_name] = dst
        
    if len(verified_files) != len(EXPECTED_HASHES):
        raise RuntimeError(f"Failed to extract all files. Got {len(verified_files)} of {len(EXPECTED_HASHES)}")
        
    print(f"\n[SUCCESS] All 3 official runtime files installed in {TARGET_DIR}!")
    
    # 4. Run upstream check
    print("\n--- 4. Running upstream setup_local.py --check-only ---")
    check_cmd = [sys.executable, "upstream_repo/setup_local.py", f"--vendor-dir={TARGET_DIR}", "--check-only"]
    check_res = subprocess.run(check_cmd, capture_output=True, text=True)
    print(check_res.stdout)
    if check_res.stderr:
        print("STDERR:", check_res.stderr)

if __name__ == "__main__":
    main()

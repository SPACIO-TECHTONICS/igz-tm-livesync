"""
Download and extract official Epic Datasmith 5.8.4 runtime for Twinmotion DirectLink
"""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.request

EXPECTED_MSI_SHA256 = "7f0e3039e9c8a772b20654342854d497c16799a92077ba2a9df0e9076f1b1927"
MSI_URL = "https://unrealstudio.epicgames.com/UnrealDatasmithRhinoExporter_5_8_400.msi"

EXPECTED_HASHES = {
    'DatasmithFacadeCSharp.dll': 'eb3e4881629244bbc3a5cb1062aa579d79f68ebb682b5140a274c7c0d1d6fc08',
    'DatasmithRhino6.rhp': '77e2073dc7bd792896f976562f97f125dd1289231338b20ef5bd8d2b6795cd1d',
    'tbbmalloc.dll': '87abcd8f7e31003ab049962a97eb645310be1ccab7ba148c46b2cde5262027bf',
}

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def main():
    # 1. Target directory
    target_dir = Path("C:/DatasmithRuntime")
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        target_dir = Path.home() / "DatasmithRuntime"
        target_dir.mkdir(parents=True, exist_ok=True)

    print(f"Target runtime directory: {target_dir}")

    # Check if files already exist and match
    all_ok = True
    for name, exp_hash in EXPECTED_HASHES.items():
        fpath = target_dir / name
        if not fpath.is_file() or sha256_file(fpath) != exp_hash:
            all_ok = False
            break

    if all_ok:
        print("[SUCCESS] All runtime files already present and verified in", target_dir)
        return

    # 2. Download MSI
    temp_dir = Path(os.environ.get("TEMP", "C:/Temp")) / "Datasmith_Extract"
    temp_dir.mkdir(parents=True, exist_ok=True)
    msi_path = temp_dir / "UnrealDatasmithRhinoExporter_5_8_400.msi"

    if msi_path.is_file() and sha256_file(msi_path) == EXPECTED_MSI_SHA256:
        print(f"Using already downloaded verified MSI: {msi_path}")
    else:
        print(f"Downloading official MSI from: {MSI_URL}")
        print("This may take 10-30 seconds (29 MB)...")
        urllib.request.urlretrieve(MSI_URL, msi_path)
        digest = sha256_file(msi_path)
        print(f"Downloaded MSI hash: {digest}")
        if digest != EXPECTED_MSI_SHA256:
            raise ValueError(f"MSI hash mismatch: got {digest}, expected {EXPECTED_MSI_SHA256}")
        print("MSI hash verified successfully.")

    # 3. Administrative unpack with msiexec
    unpack_dir = temp_dir / "unpacked"
    if unpack_dir.exists():
        shutil.rmtree(unpack_dir, ignore_errors=True)
    unpack_dir.mkdir(parents=True, exist_ok=True)

    print(f"Unpacking MSI to {unpack_dir} via administrative install...")
    cmd = f'msiexec /a "{msi_path.resolve()}" /qn TARGETDIR="{unpack_dir.resolve()}"'
    res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(f"msiexec returncode: {res.returncode}")

    # 4. Search and verify files
    found_files = {}
    for root, dirs, files in os.walk(unpack_dir):
        for f in files:
            if f in EXPECTED_HASHES:
                p = Path(root) / f
                digest = sha256_file(p)
                if digest == EXPECTED_HASHES[f]:
                    found_files[f] = p
                    print(f"  Verified matching {f}: {p} -> {digest}")
                else:
                    print(f"  Found {f} but hash did not match: {digest}")

    missing = set(EXPECTED_HASHES.keys()) - set(found_files.keys())
    if missing:
        # Fallback: check if files are named with IDs or if embedded CAB can be extracted
        print(f"Warning: Direct search missed: {missing}")
        # Search all files by hash
        for root, dirs, files in os.walk(unpack_dir):
            for f in files:
                p = Path(root) / f
                if p.is_file():
                    d = sha256_file(p)
                    for exp_name, exp_hash in EXPECTED_HASHES.items():
                        if d == exp_hash and exp_name not in found_files:
                            found_files[exp_name] = p
                            print(f"  Matched {exp_name} by hash at {p}")

    missing = set(EXPECTED_HASHES.keys()) - set(found_files.keys())
    if missing:
        raise RuntimeError(f"Could not find required runtime files in unpacked MSI: {missing}")

    # 5. Copy verified files into target_dir
    for name, src_path in found_files.items():
        dst_path = target_dir / name
        shutil.copy2(src_path, dst_path)
        print(f"Copied {name} -> {dst_path}")

    print("\n[SUCCESS] Runtime prepared successfully in:", target_dir)

    # 6. Validate with upstream setup_local.py --check-only
    upstream_setup = Path("upstream_repo/setup_local.py")
    if upstream_setup.is_file():
        print("\nRunning upstream validation check:")
        check_cmd = [sys.executable, str(upstream_setup), f"--vendor-dir={target_dir}", "--check-only"]
        check_res = subprocess.run(check_cmd, capture_output=True, text=True)
        print(check_res.stdout)
        if check_res.stderr:
            print("STDERR:", check_res.stderr)

if __name__ == "__main__":
    main()

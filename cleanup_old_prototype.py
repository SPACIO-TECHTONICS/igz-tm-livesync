"""
Safely backup and remove the obsolete prototype plugin from IngeTrazo plugins folder
"""
import os
from pathlib import Path
import shutil

plugins_dir = Path(os.environ.get('APPDATA', '')) / 'ingetrazo' / 'plugins'
old_plugin = plugins_dir / 'igz_tm_livesync'
backup_dest = Path('F:/igz-tm-livesync/backup_old_prototype')

if old_plugin.is_dir():
    print(f"Archiving old prototype from: {old_plugin}")
    if backup_dest.exists():
        shutil.rmtree(backup_dest, ignore_errors=True)
    shutil.move(str(old_plugin), str(backup_dest))
    print(f"Old prototype moved to: {backup_dest}")
else:
    print("Old prototype directory does not exist or already removed.")

print("\nRemaining plugins in IngeTrazo folder:")
for item in plugins_dir.iterdir():
    print(f"  - {item.name}")

"""
Check installed IngeTrazo plugins
"""
import os
from pathlib import Path

plugins_dir = Path(os.environ.get('APPDATA', '')) / 'ingetrazo' / 'plugins'
print(f"Plugins directory: {plugins_dir}")
if plugins_dir.is_dir():
    for item in plugins_dir.iterdir():
        print(f"  - {item.name} ({'DIR' if item.is_dir() else 'FILE'})")
else:
    print("Plugins directory does not exist.")

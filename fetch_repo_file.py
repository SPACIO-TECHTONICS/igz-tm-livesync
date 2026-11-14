"""
Fetch scene_capture.py from github repository
"""
import urllib.request
import json

url = "https://raw.githubusercontent.com/hamzah1985/ingetrazo-twinmotion-sync/main/ingetrazo_twinmotion_sync/scene_capture.py"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

try:
    with urllib.request.urlopen(req) as resp:
        content = resp.read().decode("utf-8")
        print("Successfully fetched scene_capture.py!")
        print("Length:", len(content))
        with open("scene_capture_upstream.py", "w", encoding="utf-8") as f:
            f.write(content)
        print("First 30 lines:")
        print("\n".join(content.splitlines()[:30]))
except Exception as e:
    print(f"Error fetching: {e}")

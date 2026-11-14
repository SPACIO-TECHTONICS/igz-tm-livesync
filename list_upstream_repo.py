"""
List all files in hamzah1985/ingetrazo-twinmotion-sync
"""
import urllib.request
import json

url = "https://api.github.com/repos/hamzah1985/ingetrazo-twinmotion-sync/git/trees/main?recursive=1"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print("Total files in repository:", len(data.get("tree", [])))
        for item in data.get("tree", []):
            print(" ", item["path"])
except Exception as e:
    print(f"Error: {e}")

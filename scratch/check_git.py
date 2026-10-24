import os
import shutil
import subprocess

print("shutil.which('git'):", shutil.which("git"))
print("shutil.which('gh'):", shutil.which("gh"))

search_dirs = [
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    os.path.expanduser(r"~\AppData\Local"),
    os.path.expanduser(r"~\AppData\Local\Programs"),
    os.path.expanduser(r"~\AppData\Roaming"),
    r"C:\Users\Bhavyasree s\.gemini\antigravity-ide",
]

for base in search_dirs:
    if not os.path.exists(base):
        continue
    for root, dirs, files in os.walk(base):
        if "git.exe" in files:
            print("Found git.exe at:", os.path.join(root, "git.exe"))
        if "gh.exe" in files:
            print("Found gh.exe at:", os.path.join(root, "gh.exe"))
        # limit deep recursion into massive node_modules or caches
        if any(skip in root.lower() for skip in ["node_modules", "site-packages", "cache", "temp", ".git"]):
            dirs.clear()

import os
import sys

root_dir = r"c:\Users\work\Documents\projects\C8E-Devtool\antigravity\a-vanilla\run-3\.venv\Lib\site-packages\tina4_python"

# Ensure output handles unicode
sys.stdout.reconfigure(encoding='utf-8')

for root, dirs, files in os.walk(root_dir):
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                    if "mail" in content.lower() or "smtp" in content.lower():
                        print(f"Found in {path}")
            except Exception as e:
                pass

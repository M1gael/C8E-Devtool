import sys

with open(r"c:\Users\work\Documents\projects\C8E-Devtool\antigravity\a-vanilla\run-3\.venv\Lib\site-packages\tina4_python\core\router.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# Search for "def post" or similar
for idx, line in enumerate(lines):
    if "def post(" in line or "def get(" in line:
        start = max(0, idx - 2)
        end = min(len(lines), idx + 20)
        print(f"Lines {start+1}-{end}:")
        for i in range(start, end):
            sys.stdout.buffer.write(f"  {i+1}: {lines[i].rstrip()}\n".encode('ascii', errors='replace'))
        print("-" * 20)

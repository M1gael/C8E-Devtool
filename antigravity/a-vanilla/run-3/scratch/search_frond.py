import sys

with open(r"c:\Users\work\Documents\projects\C8E-Devtool\antigravity\a-vanilla\run-3\.venv\Lib\site-packages\tina4_python\frond\engine.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "i18n" in line.lower() or "translate" in line.lower() or "t(" in line or "_(" in line:
        start = max(0, idx - 3)
        end = min(len(lines), idx + 4)
        print(f"Lines {start+1}-{end}:")
        for i in range(start, end):
            # safe print
            sys.stdout.buffer.write(f"  {i+1}: {lines[i].rstrip()}\n".encode('ascii', errors='replace'))
        print("-" * 20)

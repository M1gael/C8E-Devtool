with open(r"c:\Users\work\Documents\projects\C8E-Devtool\antigravity\a-vanilla\run-3\.venv\Lib\site-packages\tina4_python\core\router.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if "auth_required" in line or "secured" in line or "noauth" in line:
        start = max(0, idx - 4)
        end = min(len(lines), idx + 5)
        print(f"Lines {start+1}-{end}:")
        for i in range(start, end):
            print(f"  {i+1}: {lines[i].rstrip()}")
        print("-" * 20)

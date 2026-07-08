with open(r"c:\Users\work\Documents\projects\C8E-Devtool\antigravity\a-vanilla\run-3\.venv\Lib\site-packages\tina4_python\core\server.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx in range(1220, 1260):
    print(f"  {idx+1}: {lines[idx].rstrip()}")

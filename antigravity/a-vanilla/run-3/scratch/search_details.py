def print_context(path):
    print(f"=== {path} ===")
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for idx, line in enumerate(lines):
        if "cookie_header" in line or "session" in line:
            start = max(0, idx - 3)
            end = min(len(lines), idx + 4)
            print(f"Lines {start+1}-{end}:")
            for i in range(start, end):
                print(f"  {i+1}: {lines[i].rstrip()}")
            print("-" * 20)

print_context(r"c:\Users\work\Documents\projects\C8E-Devtool\antigravity\a-vanilla\run-3\.venv\Lib\site-packages\tina4_python\core\server.py")

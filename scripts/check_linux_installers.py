"""Print only IDs/names of active Linux Python package installers."""
from pathlib import Path
import json
import os

rows = []
for item in Path('/proc').iterdir():
    if not item.name.isdigit() or int(item.name) == os.getpid():
        continue
    try:
        args = [x.decode(errors='replace') for x in (item / 'cmdline').read_bytes().split(b'\0') if x]
        if not args:
            continue
        exe = Path(args[0]).name
        pip = exe in ('pip', 'pip3', 'uv')
        pip = pip or (exe.startswith('python') and any(args[i:i+2] == ['-m', 'pip'] for i in range(len(args)-1)))
        if pip:
            rows.append(dict(pid=int(item.name), name=exe))
    except (OSError, PermissionError):
        pass
print(json.dumps(dict(active_installers=rows)))
raise SystemExit(1 if rows else 0)

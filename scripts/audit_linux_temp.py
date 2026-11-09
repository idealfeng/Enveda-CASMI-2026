"""Inspect only the pip temp directories observed during this task."""
from pathlib import Path
import json
import os

names = '''pip-build-tracker-99ek26ez pip-ephem-wheel-cache-a40lax7r pip-install-g5z2tue9
pip-metadata-1mm7qj22 pip-metadata-5nlt8i5j pip-metadata-6jjdcrb1
pip-metadata-89ez44t1 pip-metadata-9jw3iet6 pip-metadata-9l3i67k0
pip-metadata-bvwrf3r_ pip-metadata-ozh6c4gv pip-metadata-rfbm0q2g
pip-metadata-tvblul55 pip-metadata-vug405h3 pip-unpack-0b8alpe3
pip-unpack-17guje7_ pip-unpack-3ci9oyoh pip-unpack-3e5_68r4
pip-unpack-5brv6g2f pip-unpack-6_80o7e_ pip-unpack-8pg3rxp2
pip-unpack-8rehzvmk pip-unpack-b3881w89 pip-unpack-cgpinb4x
pip-unpack-fdjgubqh pip-unpack-fgjn9tfl pip-unpack-g39e4stu
pip-unpack-g7uy9y9a pip-unpack-hd9ebv0j pip-unpack-hgce5ee9
pip-unpack-ig10sbna pip-unpack-oycgk_pi pip-unpack-t03g4oxw
pip-unpack-unla8a4n pip-unpack-vcb87ehi pip-unpack-vcw5u18h
pip-unpack-vjs29fat pip-unpack-vz62xxmm pip-unpack-w1fw6atm
pip-unpack-w7xl6h8n pip-unpack-zq1iptfi'''.split()
remaining = []
for name in names:
    path = Path('/tmp')/name
    if path.exists():
        remaining.append({'path':str(path),'bytes':sum(x.stat().st_size for x in path.rglob('*') if x.is_file())})
processes=[]
for path in Path('/proc').glob('[0-9]*/cmdline'):
    try:
        cmd=path.read_bytes().replace(b'\0',b' ').decode()
        if '.venv-linux/bin/python -m pip install' in cmd:
            processes.append({'pid':int(path.parent.name),'command':cmd})
    except (PermissionError,FileNotFoundError,ProcessLookupError):
        pass
report={'observed_task_temp_paths_remaining':remaining,'remaining_bytes':sum(x['bytes'] for x in remaining),
        'project_pip_processes':processes,'TMPDIR':os.environ.get('TMPDIR')}
root=Path(__file__).resolve().parents[1]
(root/'reports/linux_temp_audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))

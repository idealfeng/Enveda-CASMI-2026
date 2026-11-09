from datetime import datetime,timezone
import json
from pathlib import Path

target='scripts/audit_external_reference_increment.py'
known_pids=[481,501,502,503,504]
matches=[]
known={}
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():
        continue
    try:
        args=(proc/'cmdline').read_bytes().replace(b'\x00',b' ').decode(errors='replace').strip()
        if target in args:
            matches.append({'pid':int(proc.name),'command':args})
        if int(proc.name) in known_pids:
            known[proc.name]={'present':True,'same_task':target in args,'command':args}
    except (FileNotFoundError,ProcessLookupError,PermissionError):
        pass
for pid in known_pids:
    known.setdefault(str(pid),{'present':False,'same_task':False})
receipt={'checked_at_utc':datetime.now(timezone.utc).isoformat(),
    'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
    'checked_script':target,'known_parent_and_worker_pids':known,
    'all_matching_script_processes':matches,'no_lingering_jobs':not matches,
    'action':'read_only_full_proc_command_line_scan; no processes killed'}
Path('reports/external_reference_pilot_20261107/no_lingering_jobs.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
assert receipt['no_lingering_jobs']

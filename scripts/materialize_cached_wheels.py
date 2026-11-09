"""Expose complete cached Linux wheels for an offline interrupted-install resume."""
from pathlib import Path
from email.parser import BytesParser
import json
import os
import zipfile

root=Path(__file__).resolve().parents[1]
cache=root/'.cache/pip-linux'
output=root/'.cache/wheels-linux'
output.mkdir(parents=True,exist_ok=True)
results=[]
for path in cache.rglob('*.body'):
    if path.stat().st_size<1024:
        continue
    with path.open('rb') as handle:
        if handle.read(4)!=b'PK\x03\x04':
            continue
    try:
        with zipfile.ZipFile(path) as archive:
            names=archive.namelist()
            wheel=next((x for x in names if x.endswith('.dist-info/WHEEL')),None)
            if not wheel:
                continue
            metadata=wheel.rsplit('/',1)[0]+'/METADATA'
            info=BytesParser().parsebytes(archive.read(metadata))
            wheel_info=BytesParser().parsebytes(archive.read(wheel))
            name=info['Name'].replace('-','_').replace('.','_')
            version=info['Version']
            tag=wheel_info.get_all('Tag')[0]
            build=wheel_info.get('Build')
            filename=f'{name}-{version}-'+(f'{build}-' if build else '')+tag+'.whl'
        target=output/filename
        if not target.exists():
            os.link(path,target)
        results.append({'file':filename,'bytes':target.stat().st_size})
    except (zipfile.BadZipFile,KeyError,TypeError):
        continue
(root/'reports/cached_linux_wheels.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({'wheels':len(results),'bytes':sum(x['bytes'] for x in results),'directory':str(output)}))

"""Fetch the small official MSG compact archive and extract identity metadata only."""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
import hashlib
import json
import tarfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets/research/mist_msg_20261114/exposure'
REPORT=ROOT/'reports/mist_evaluation_20261114'
SIZE=15682874
SHA='a19e657a802cf5869d97b3486c7ce41021cba9c9a6279818e5d186307e3e7a35'
MD5='13e86837ee49ea81e15f3d096cc636ec'
URL='https://zenodo.org/records/23303289/files/msg_compact.tar.gz'

def main():
    OUT.mkdir(parents=True,exist_ok=True);REPORT.mkdir(parents=True,exist_ok=True)
    target=OUT/'msg_compact.tar.gz'
    if not target.exists():
        temporary=OUT/'msg_compact.tar.gz.part';count=0
        with urllib.request.urlopen(URL,timeout=60) as response,temporary.open('wb') as handle:
            while chunk:=response.read(1<<20):
                count+=len(chunk)
                if count>SIZE:raise ValueError('Official compact archive size exceeded')
                handle.write(chunk)
        if count!=SIZE:raise ValueError('Incomplete compact archive')
        temporary.replace(target)
    raw=target.read_bytes()
    if len(raw)!=SIZE or hashlib.sha256(raw).hexdigest()!=SHA or hashlib.md5(raw).hexdigest()!=MD5:
        raise ValueError('Official compact archive checksum mismatch')
    files=[];total=0
    with tarfile.open(target,'r:gz') as archive:
        for member in archive:
            path=PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or member.issym() or member.islnk():
                raise ValueError('Unsafe archive member')
            if not member.isfile() or path.name not in ('structure_ids.npy','names.npy','manifest.json'):continue
            if not 0<=member.size<=32<<20:raise ValueError('Unexpected metadata member size')
            total+=member.size
            if total>96<<20:raise ValueError('Metadata extraction cap')
            destination=(OUT/'metadata'/Path(*path.parts)).resolve()
            if not destination.is_relative_to(OUT.resolve()):raise ValueError('Extraction escape')
            source=archive.extractfile(member)
            data=source.read(member.size+1)
            if len(data)!=member.size:raise ValueError('Metadata member length mismatch')
            if destination.exists() and destination.read_bytes()!=data:raise ValueError('Preserve existing metadata')
            destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(data)
            files.append(dict(path=destination.relative_to(ROOT).as_posix(),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    if not any(Path(f['path']).name=='structure_ids.npy' for f in files):raise ValueError('No structure identity metadata')
    result=dict(status='downloaded_verified_identity_metadata',checked_at_utc=datetime.now(timezone.utc).isoformat(),
                source=URL,bytes=SIZE,sha256=SHA,md5=MD5,files=files,downloaded_fingerprint_targets=False,
                note='Archive contains labels but only names/structure_ids/manifests extracted. Membership identities are raw InChIKey14, not yet official tautomer-canonical identities.')
    (REPORT/'exposure_download.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status=result['status'],metadata_files=len(files),metadata_bytes=total)))

if __name__=='__main__':main()

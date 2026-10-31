"""Create a local private migration archive. Never upload the archive to GitHub."""
from pathlib import Path
import json
import zipfile

root=Path(__file__).resolve().parents[1]
paths=[root/p for p in ('backend/.env','backend/credentials.json','.demo/access.json','.demo/render.env')]
for folder in ('backend/storage/tenants','storage/tenants'):
    base=root/folder
    if base.exists(): paths.extend(p for p in base.rglob('*') if p.is_file())
files=[p for p in paths if p.is_file()]
if not (root/'backend/.env').is_file(): raise SystemExit('backend/.env is missing; migration cannot preserve the connection settings.')
out=root/'.demo/laptop.private.zip'
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:
    for p in files: archive.write(p,p.relative_to(root).as_posix())
    archive.writestr('PRIVATE_TRANSFER_NOTICE.txt','PRIVATE: contains database credentials, Google service key and demo passwords. Transfer directly to your own laptop. Do not upload to GitHub or send to customers. Extract into the cloned repository root. Local virtual environments and node_modules must be reinstalled. Cloud database and Google Drive are not copied or reset. Archive is not encrypted.\n')
print('Private archive:',out)
print('Files included:',len(files))
print('Archive is not encrypted. Transfer privately; never commit it.')

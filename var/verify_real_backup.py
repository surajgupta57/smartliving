import gzip,hashlib,json,re,tarfile
from pathlib import Path
root=Path('var/private_backups')
backup=sorted(path for path in root.iterdir() if path.is_dir())[-1]
manifest=json.loads((backup/'manifest.json').read_text())
assert not (backup/'INCOMPLETE').exists()
for name,expected in manifest['sha256'].items():
    with (backup/name).open('rb') as source:assert hashlib.file_digest(source,'sha256').hexdigest()==expected
with gzip.open(backup/'database.sql.gz','rb') as source:
    sql=source.read()
    assert b'CREATE TABLE' in sql
    assert not re.search(rb'(?m)^(USE `|CREATE DATABASE)',sql)
for name in ['media','private_documents']:
    with tarfile.open(backup/(name+'.tar.gz')) as archive:
        members=archive.getmembers()
        assert all(not m.issym() and not m.islnk() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in members)
        print(name,'archive validated:',len(members),'entries')
print('Real local MySQL backup checksums and archives passed. SQL has no CREATE DATABASE / USE directives. A separate-database restore rehearsal is still required.')

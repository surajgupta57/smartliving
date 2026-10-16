from io import BytesIO,StringIO
from pathlib import Path
import gzip,json,secrets,subprocess,sys,tempfile,tarfile,zipfile
from types import SimpleNamespace
from unittest.mock import patch
from django.core.management import call_command,CommandError
from django.test import SimpleTestCase
from apps.core.management.commands.backup_site import mysql_option,private_backup_root
from scripts.build_release import build

ROOT=Path(__file__).resolve().parents[2]


class ProductionToolTests(SimpleTestCase):
    def test_environment_generator_refuses_overwrite_and_does_not_print_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'production.env'
            command=[sys.executable,str(ROOT/'scripts/init_production_env.py'),'--output',str(target)]
            response=subprocess.run(command,capture_output=True,text=True,timeout=15)
            self.assertEqual(response.returncode,0,response.stderr)
            text=target.read_text()
            secret=next(line.split('=',1)[1] for line in text.splitlines() if line.startswith('DJANGO_SECRET_KEY='))
            self.assertGreaterEqual(len(secret),50)
            self.assertNotIn(secret,response.stdout+response.stderr)
            again=subprocess.run(command,capture_output=True,text=True,timeout=15)
            self.assertNotEqual(again.returncode,0)
            self.assertEqual(target.read_text(),text)

    def test_release_excludes_private_and_generated_files_and_has_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'release.zip'
            build(ROOT,target)
            with zipfile.ZipFile(target) as archive:
                names=archive.namelist()
                self.assertIn('config/production.py',names)
                self.assertIn('deploy/cpanel/passenger_wsgi.py',names)
                self.assertIn('.env.production.example',names)
                self.assertFalse(any(name in names for name in ['.env','.env.production','db.sqlite3','smartliving-catalogue-500.zip']))
                self.assertFalse(any(name.startswith(('media/','var/','tmp/','staticfiles/','output/','.venv/')) for name in names))
                self.assertFalse(any('..' in Path(name).parts for name in names))
            self.assertTrue(target.with_suffix('.sha256').is_file())

    def test_backup_credentials_are_not_in_argv_and_files_are_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            media=base/'media';documents=base/'documents';static=base/'static'
            for folder in [media,documents,static]:folder.mkdir()
            (media/'image.txt').write_text('image test');(documents/'document.txt').write_text('private test')
            secret='test\\password"with#special'
            fake_settings=SimpleNamespace(ENVIRONMENT='production',MEDIA_ROOT=media,PRIVATE_DOCUMENT_ROOT=documents,STATIC_ROOT=static,DATABASES={'default':{'ENGINE':'django.db.backends.mysql','USER':'test_user','PASSWORD':secret,'HOST':'localhost','PORT':3306,'NAME':'test_db'}})
            process=SimpleNamespace(stdout=BytesIO(b'-- test SQL\nCREATE TABLE test (id int);'),wait=lambda:0,poll=lambda:0)
            captured=[]
            def popen(arguments,**kwargs):
                captured.extend(arguments)
                config=Path(arguments[1].split('=',1)[1])
                self.assertTrue(config.exists())
                self.assertIn(mysql_option(secret),config.read_text())
                self.assertNotIn(secret,' '.join(arguments))
                return process
            with patch('apps.core.management.commands.backup_site.settings',fake_settings),patch('apps.core.management.commands.backup_site.shutil.which',return_value='/mock/mysqldump'),patch('apps.core.management.commands.backup_site.subprocess.Popen',side_effect=popen):
                call_command('backup_site',output_dir=str(base/'backups'),stdout=StringIO())
            backup=next((base/'backups').iterdir())
            self.assertFalse((backup/'INCOMPLETE').exists())
            self.assertEqual(gzip.open(backup/'database.sql.gz','rb').read(),b'-- test SQL\nCREATE TABLE test (id int);')
            self.assertEqual(set(json.loads((backup/'manifest.json').read_text())['sha256']),{'database.sql.gz','media.tar.gz','private_documents.tar.gz'})
            with tarfile.open(backup/'private_documents.tar.gz') as archive:self.assertIn('private_documents/document.txt',archive.getnames())
            self.assertFalse(list(backup.glob('smartliving-backup-*')))
            self.assertNotIn('--databases',captured)

    def test_backup_rejects_public_and_recursive_storage_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            fake_settings=SimpleNamespace(MEDIA_ROOT=base/'media',STATIC_ROOT=base/'static',PRIVATE_DOCUMENT_ROOT=base/'documents')
            with patch('apps.core.management.commands.backup_site.settings',fake_settings):
                for path in [base/'media'/'backup',base/'documents'/'backup',base/'public_html'/'backup']:
                    with self.assertRaises(CommandError):private_backup_root(path)

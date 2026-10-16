import os,secrets,subprocess,sys,shutil
from pathlib import Path
root=Path(__file__).resolve().parents[1]
env=os.environ.copy();env.update({'DJANGO_ENV':'production','DJANGO_SETTINGS_MODULE':'config.production','DJANGO_SECRET_KEY':secrets.token_urlsafe(64),'DJANGO_ALLOWED_HOSTS':'smartliving.seas-india.com','DJANGO_CSRF_TRUSTED_ORIGINS':'https://smartliving.seas-india.com','DJANGO_SECURE_SSL_REDIRECT':'True'})
if shutil.disk_usage(root).free<2*1024**3:raise SystemExit('Insufficient free space for a backup test')
result=subprocess.run([sys.executable,'manage.py','backup_site','--output-dir',str(root/'var/private_backups'),'--mysqldump',r'C:\Program Files\MySQL\MySQL Server 8.0\bin\mysqldump.exe','--settings=config.production'],cwd=root,env=env,capture_output=True,text=True,timeout=240)
print(result.stdout.strip());print(result.stderr.strip());raise SystemExit(result.returncode)

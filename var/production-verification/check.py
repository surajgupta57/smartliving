import os,secrets,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
work=root/'var'/'production-verification'
env={k:v for k,v in os.environ.items() if not k.startswith('DJANGO_') and not k.startswith('DB_')}
env.update({'DJANGO_ENV_FILE':str(work/'absent.env'),'DJANGO_SETTINGS_MODULE':'config.production','DJANGO_ENV':'production','DJANGO_SECRET_KEY':secrets.token_urlsafe(64),'DJANGO_DEBUG':'True','DJANGO_ALLOWED_HOSTS':'smartliving.seas-india.com','DJANGO_CSRF_TRUSTED_ORIGINS':'https://smartliving.seas-india.com','DJANGO_DB_ENGINE':'mysql','DB_NAME':'offline_verification','DB_USER':'offline_verification','DB_PASSWORD':secrets.token_urlsafe(32),'DJANGO_SECURE_SSL_REDIRECT':'True','DJANGO_STATIC_ROOT':str(work/'static'),'DJANGO_MEDIA_ROOT':str(work/'media'),'DJANGO_PRIVATE_IMPORT_ROOT':str(work/'private_imports'),'DJANGO_PRIVATE_DOCUMENT_ROOT':str(work/'private_documents')})
for name in ['media','private_imports','private_documents']:(work/name).mkdir(exist_ok=True)
for args in [['check','--deploy'],['production_check','--configuration-only'],['collectstatic','--noinput','--verbosity','0']]:
    result=subprocess.run([sys.executable,'manage.py',*args],cwd=root,env=env,capture_output=True,text=True,timeout=120)
    print(' '.join(args), 'PASS' if result.returncode==0 else 'FAILED')
    if result.returncode:
        print(result.stdout,result.stderr)
        raise SystemExit(result.returncode)
print('Strict production settings passed without database access; production manifest collected separately from local assets.')

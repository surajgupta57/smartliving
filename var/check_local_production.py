import os,secrets,sys,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
env=os.environ.copy()
env.update({'DJANGO_ENV':'production','DJANGO_SETTINGS_MODULE':'config.production','DJANGO_SECRET_KEY':secrets.token_urlsafe(64),'DJANGO_ALLOWED_HOSTS':'smartliving.seas-india.com','DJANGO_CSRF_TRUSTED_ORIGINS':'https://smartliving.seas-india.com','DJANGO_SECURE_SSL_REDIRECT':'True','DJANGO_STATIC_ROOT':str(root/'var'/'production-verification'/'static'),'SMARTLIVING_PROJECT_ROOT':str(root)})
for args in [[str(root/'deploy'/'cpanel'/'passenger_wsgi.py')],['manage.py','production_check','--settings=config.production']]:
    result=subprocess.run([sys.executable,*args],cwd=root,env=env,capture_output=True,text=True,timeout=60)
    print('Passenger import' if len(args)==1 else 'Read-only full preflight on configured local MySQL','PASS' if result.returncode==0 else 'NEEDS OPERATOR SETUP')
    if result.stdout:print(result.stdout.strip())
    if result.returncode:print(result.stderr.strip())

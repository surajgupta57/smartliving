r"""Run interactively: .\.venv\Scripts\python.exe scripts/setup_local_mysql.py"""
import json
import getpass
import os
from pathlib import Path
import secrets
import subprocess
import sys

import MySQLdb

ROOT = Path(__file__).resolve().parent.parent


def run(*args, env):
    subprocess.run([sys.executable, str(ROOT / "manage.py"), *args], cwd=ROOT, env=env, check=True)


def main():
    env_file = ROOT / ".env"
    if env_file.exists():
        raise SystemExit("An .env file already exists. Preserve and review it before running setup.")
    host = input("MySQL host [127.0.0.1]: ").strip() or "127.0.0.1"
    port = int(input("MySQL port [3306]: ").strip() or "3306")
    admin = input("MySQL administrator user [root]: ").strip() or "root"
    password = getpass.getpass("MySQL administrator password (hidden): ")
    conn = MySQLdb.connect(host=host, port=port, user=admin, passwd=password, connect_timeout=5)
    del password
    app_password = secrets.token_urlsafe(36)
    with conn.cursor() as cursor:
        cursor.execute("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA WHERE SCHEMA_NAME='smartliving'")
        if cursor.fetchone():
            raise SystemExit("Database smartliving already exists; stopped without changing it.")
        cursor.execute("SELECT 1 FROM mysql.user WHERE User='smartliving_app' AND Host='localhost'")
        if cursor.fetchone():
            raise SystemExit("User smartliving_app already exists; stopped without changing it.")
        cursor.execute("CREATE DATABASE smartliving CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cursor.execute("CREATE USER 'smartliving_app'@'localhost' IDENTIFIED BY %s", (app_password,))
        cursor.execute("GRANT ALL PRIVILEGES ON smartliving.* TO 'smartliving_app'@'localhost'")
    conn.close()
    sqlite_env = dict(os.environ, DJANGO_DB_ENGINE="sqlite")
    fixture = ROOT / "var" / "mysql-transfer.json"
    fixture.parent.mkdir(exist_ok=True)
    try:
        run("dumpdata", "--natural-foreign", "--natural-primary", "--exclude=contenttypes", "--exclude=auth.permission", "--exclude=sessions", "--exclude=catalogue.productsearchtoken", "--output", str(fixture), env=sqlite_env)
        expected_products = sum(row["model"] == "catalogue.product" for row in json.loads(fixture.read_text(encoding="utf-8")))
        mysql_env = dict(os.environ, DJANGO_DB_ENGINE="mysql", DB_NAME="smartliving", DB_USER="smartliving_app", DB_PASSWORD=app_password, DB_HOST=host, DB_PORT=str(port))
        # Save generated credentials before migration so any failure can be resumed.
        env_file.write_text("\n".join(f"{key}={mysql_env[key]}" for key in ("DJANGO_DB_ENGINE", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT")) + "\n", encoding="utf-8")
        run("migrate", "--noinput", env=mysql_env)
        run("loaddata", str(fixture), env=mysql_env)
        run("rebuild_product_search", env=mysql_env)
        run("check", env=mysql_env)
        verification = (
            "from apps.catalogue.models import Product; "
            f"assert Product.objects.count() == {expected_products}; "
            "from django.test import Client; "
            "c=Client(HTTP_HOST='localhost'); "
            "assert c.get('/products/').status_code == 200; "
            "assert c.get('/search/suggestions/', {'q':'camera'}).status_code == 200; "
            "print('MySQL product count and public endpoints verified.')"
        )
        run("shell", "-c", verification, env=mysql_env)
    finally:
        fixture.unlink(missing_ok=True)
    print("MySQL configured. Credentials are in .env; SQLite was retained. Restart Django.")


if __name__ == "__main__":
    main()

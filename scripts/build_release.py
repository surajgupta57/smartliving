"""Build an allowlisted source release, excluding credentials and business data."""
import argparse
import hashlib
from pathlib import Path
import zipfile


def release_files(root, include_catalogue=False):
    directories = ['apps', 'config', 'templates', 'static', 'deploy/cpanel']
    selected = []
    for directory in directories:
        for path in (root / directory).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix not in {'.pyc', '.pyo'}:
                if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
                    raise ValueError('Release inputs must not contain symlinks or paths outside the source root.')
                selected.append(path)
    for name in ['manage.py', 'requirements.txt', 'requirements-mysql.txt', 'requirements-production.txt', '.env.production.example', 'README.md',
                 'docs/PRODUCTION_DEPLOYMENT_GUIDE.md', 'docs/PRODUCTION_LAUNCH.md', 'docs/PRODUCTION_READINESS.md',
                 'docs/GODADDY_CPANEL_LAUNCH.md', 'docs/BUSINESS_CONTENT_DEPLOYMENT.md',
                 'deploy/__init__.py', 'deploy/deploy.py', 'deploy/deploy.example.json', 'deploy/README.md',
                 'scripts/init_production_env.py', 'scripts/build_release.py', 'scripts/smoke_production.py']:
        selected.append(root / name)
    if include_catalogue:
        import json
        bundle = root / 'catalogue_seed' / 'manufacturers'
        manifest = json.loads((bundle / 'manifest.json').read_text(encoding='utf-8'))
        selected += [bundle / 'manifest.json', bundle / 'README.md']
        for product in manifest['products']:
            selected += [bundle / asset['path'] for asset in product['images'] + product['documents']]
    for path in selected:
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('A required release file is missing or unsafe.')
        if path.name.startswith('.env') and path.name != '.env.production.example':
            raise ValueError('Credentials may not be included in a release.')
    return sorted(set(selected))


def build(root, output, include_catalogue=False):
    files = release_files(root, include_catalogue)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(root).as_posix())
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.sha256').write_text(f'{digest}  {output.name}\n', encoding='utf-8')
    return len(files)


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=root / 'deploy' / 'releases' / 'smartliving-production.zip')
    parser.add_argument('--include-catalogue', action='store_true', help='Include referenced manufacturer seed assets; never include live media or business records.')
    args = parser.parse_args()
    count = build(root, args.output.absolute(), args.include_catalogue)
    print(f'Release written: {count} allowlisted files; secrets, databases, live media and generated outputs excluded.')


if __name__ == '__main__':
    main()

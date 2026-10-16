"""Create a private production template without displaying its generated secret."""
import argparse
import os
from pathlib import Path
import secrets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='Private destination; existing files are never overwritten.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    text = (root / '.env.production.example').read_text(encoding='utf-8')
    text = text.replace('REPLACE_WITH_A_UNIQUE_RANDOM_SECRET_AT_LEAST_50_CHARACTERS', secrets.token_urlsafe(64))
    destination = args.output.expanduser().absolute()
    if any(part.lower() in {'public_html', 'htdocs', 'httpdocs', 'www'} for part in destination.parts) or any((root / folder).resolve() in destination.resolve().parents for folder in ['static', 'staticfiles', 'media']):
        parser.error('The production environment file must be outside public/static/media directories.')
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)
    print('Private production template created. Fill database values privately; the secret was not displayed. Existing local settings were not changed.')


if __name__ == '__main__':
    main()

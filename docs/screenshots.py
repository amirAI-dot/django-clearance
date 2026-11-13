"""
The documentation's pictures of the admin site, taken from the example shop.

    nox -s screenshots

The example project is copied to a folder of its own, given a fresh database
and its sample people and orders - and a rule scope and a bundle's name in
Persian, so no page is empty - then served, and each page is
opened in a real browser, in English and in Persian, and saved to
docs/img/<language>/<name>.png. Run it again whenever a page changes: a
picture is never taken by hand, so none falls behind the pages it shows.
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PICTURES = ROOT / 'docs' / 'img'
SIZE = {'width': 1280, 'height': 800}
LANGUAGES = {'en': 'en-US', 'fa': 'fa-IR'}
SUPERUSER = ('admin', 'only-for-the-pictures')

#: What the sample data needs beyond example_data, and the keys the pages use.
SETUP = """
import json
from django.contrib.auth.models import Group
from clearance.roles.models import Role
from clearance.services import AccessService
from clearance.translations.services import TranslationService
from shop.models import Order, Person

access = AccessService(actor=None)
rule = access.create_scope_rule(
    Order,
    'open',
    'Open orders',
    [{'field': 'status', 'operator': 'is_one_of', 'value': {'constant': ['pending', 'approved']}}],
)
managers = Group.objects.get(name='Branch managers')
# "Branch managers", in Persian - written as escapes: the code is English only.
TranslationService(actor=None).name(
    managers, 'fa', '\\u0645\\u062f\\u06cc\\u0631\\u0627\\u0646 \\u0634\\u0639\\u0628\\u0647'
)
print(json.dumps({
    'bundle': managers.pk,
    'person': Person.objects.get(username='north_manager').pk,
    'rule': rule.pk,
    'role': Role.objects.get(code='manager').pk,
    'order': Order.objects.filter(branch__name='North').first().pk,
}))
"""


#: The pictures that show a part of a long page, by the text the part starts at.
FOCUS = {'bundle': 'Shop: orders'}


def pages(keys: dict[str, int]) -> dict[str, tuple[str, str]]:
    """``{picture: (who, address)}`` - each page, and who is signed in to see it."""
    return {
        'overview': ('admin', '/admin/access/'),
        'bundles': ('admin', '/admin/access/bundles/'),
        'bundle': ('admin', f'/admin/access/bundles/{keys["bundle"]}/'),
        'people': ('admin', '/admin/access/people/'),
        'person': ('admin', f'/admin/access/people/{keys["person"]}/'),
        'permissions': ('admin', '/admin/access/permissions/'),
        'scopes': ('admin', '/admin/access/scopes/'),
        'scope': ('admin', f'/admin/access/scopes/{keys["rule"]}/'),
        'fields': ('admin', '/admin/access/fields/'),
        'fields-of-order': ('admin', '/admin/access/fields/shop.Order/'),
        'actions': ('admin', '/admin/access/actions/'),
        'roles': ('admin', '/admin/access/roles/'),
        'role': ('admin', f'/admin/access/roles/{keys["role"]}/'),
        'names': ('admin', f'/admin/access/names/auth.group/{keys["bundle"]}/'),
        'orders-as-a-manager': ('north_manager', '/admin/shop/order/'),
        'order-as-a-manager': ('north_manager', f'/admin/shop/order/{keys["order"]}/change/'),
    }


def main() -> None:
    with tempfile.TemporaryDirectory() as folder:
        project = Path(folder) / 'example'
        shutil.copytree(ROOT / 'example', project, ignore=shutil.ignore_patterns('db.sqlite3'))
        keys = prepare(project)
        port = free_port()
        server = subprocess.Popen(
            [sys.executable, 'manage.py', 'runserver', '--noreload', f'127.0.0.1:{port}'],
            cwd=project,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            wait_for(f'http://127.0.0.1:{port}/admin/login/')
            photograph(f'http://127.0.0.1:{port}', pages(keys))
        finally:
            server.terminate()
            server.wait()


def prepare(project: Path) -> dict[str, int]:
    """The example's database, its sample data and the superuser - and the keys of its rows."""
    username, password = SUPERUSER
    environment = {
        **os.environ,
        'DJANGO_SUPERUSER_USERNAME': username,
        'DJANGO_SUPERUSER_PASSWORD': password,
        'DJANGO_SUPERUSER_EMAIL': 'admin@example.com',
    }

    for command in (['migrate'], ['example_data'], ['createsuperuser', '--noinput']):
        manage(project, command, environment)

    return json.loads(manage(project, ['shell', '-c', SETUP], environment).strip().splitlines()[-1])


def manage(project: Path, command: list[str], environment: dict[str, str]) -> str:
    done = subprocess.run(
        [sys.executable, 'manage.py', *command, '--verbosity=0'],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout


def photograph(server: str, shown: dict[str, tuple[str, str]]) -> None:
    with sync_playwright() as driver:
        browser = driver.chromium.launch()

        for language, locale in LANGUAGES.items():
            folder = PICTURES / language
            folder.mkdir(parents=True, exist_ok=True)
            signed_in: dict[str, Page] = {}

            for picture, (who, address) in shown.items():
                if who not in signed_in:
                    context = browser.new_context(locale=locale, viewport=SIZE)
                    signed_in[who] = sign_in(context.new_page(), server, who)

                page = signed_in[who]
                page.goto(f'{server}{address}')

                if picture in FOCUS:
                    part = page.get_by_text(FOCUS[picture], exact=True).first
                    part.evaluate("node => node.scrollIntoView({block: 'start'})")
                    page.evaluate('window.scrollBy(0, -120)')  # the column headings above it

                page.screenshot(path=folder / f'{picture}.png')
                print(f'{language}/{picture}.png')

        browser.close()


def sign_in(page: Page, server: str, who: str) -> Page:
    """``who`` signed in - the superuser, or a sample person, whose password is their name."""
    password = SUPERUSER[1] if who == SUPERUSER[0] else who
    page.goto(f'{server}/admin/login/')
    page.fill('input[name="username"]', who)
    page.fill('input[name="password"]', password)
    page.click('input[type="submit"]')
    page.wait_for_url(f'{server}/admin/')
    return page


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port: int = probe.getsockname()[1]
        return port


def wait_for(address: str, seconds: float = 30) -> None:
    deadline = time.monotonic() + seconds

    while True:
        try:
            with urllib.request.urlopen(address):
                return
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.2)


if __name__ == '__main__':
    main()

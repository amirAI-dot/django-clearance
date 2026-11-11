"""
The library ships Persian: every string it marks is translated in the
catalogue of the app that marks it, and the compiled catalogue says what the
source says.

If these fail, a Persian administrator reads an English sentence in the
middle of a Persian page, a message loses the name it was meant to show, or
a catalogue edited and not compiled serves the old translation - which looks
right to whoever reads the ``.po`` and is wrong on every screen.

That every marked string is in a catalogue at all is held by ``nox -s
messages``, which extracts them again and finds nothing new.
"""

import ast
import gettext
import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from django.test import Client, override_settings
from django.utils import translation
from django.utils.translation import gettext as _

from tests.conftest import MakeUser

SOURCE = Path(__file__).resolve().parent.parent / 'src' / 'clearance'
CATALOGUES = sorted(SOURCE.rglob('locale/fa/LC_MESSAGES/django.po'))
PLACEHOLDER = re.compile(r'%\((\w+)\)[sd]')

#: "Bundles", in Persian - written as escapes: the code is English only.
BUNDLES_FA = '\u0628\u0633\u062a\u0647\u200c\u0647\u0627'
#: "What it is for" - a string only the translations app marks.
WHAT_FOR_FA = '\u0628\u0631\u0627\u06cc \u0686\u06cc\u0633\u062a'


@dataclass
class Entry:
    msgid: str = ''
    msgid_plural: str = ''
    msgstr: dict[int, str] = field(default_factory=dict)
    flags: set[str] = field(default_factory=set)


def entries(path: Path) -> list[Entry]:
    """The entries of a ``.po`` file, the header left out."""
    found: list[Entry] = []
    current, key = Entry(), ''

    def close() -> None:
        nonlocal current
        if current.msgid or current.msgstr:
            found.append(current)
        current = Entry()

    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            close()
        elif line.startswith('#,'):
            current.flags |= {flag.strip() for flag in line[2:].split(',')}
        elif line.startswith('#'):
            continue
        elif line.startswith('"'):
            text = ast.literal_eval(line)
            if key.startswith('msgstr'):
                index = int(key[7:-1]) if '[' in key else 0
                current.msgstr[index] += text
            else:
                setattr(current, key, getattr(current, key) + text)
        else:
            key, _, rest = line.partition(' ')
            text = ast.literal_eval(rest)
            if key.startswith('msgstr'):
                current.msgstr[int(key[7:-1]) if '[' in key else 0] = text
            else:
                setattr(current, key, text)

    close()
    return [entry for entry in found if entry.msgid]


def named(path: Path) -> str:
    return str(path.relative_to(SOURCE))


def test_there_is_a_catalogue_for_every_app() -> None:
    assert [named(path) for path in CATALOGUES] == [
        'locale/fa/LC_MESSAGES/django.po',
        'roles/locale/fa/LC_MESSAGES/django.po',
        'translations/locale/fa/LC_MESSAGES/django.po',
    ]


@pytest.mark.parametrize('path', CATALOGUES, ids=named)
def test_every_entry_is_translated_and_keeps_its_placeholders(path: Path) -> None:
    problems = []

    for entry in entries(path):
        sources = [entry.msgid, entry.msgid_plural] if entry.msgid_plural else [entry.msgid]

        if 'fuzzy' in entry.flags:
            problems.append(f'{entry.msgid!r} is fuzzy')

        for index, source in enumerate(sources):
            words = entry.msgstr.get(index, '')
            if not words:
                problems.append(f'{entry.msgid!r} has no translation [{index}]')
            elif set(PLACEHOLDER.findall(words)) != set(PLACEHOLDER.findall(source)):
                problems.append(f'{entry.msgid!r} loses or adds a placeholder [{index}]')

    assert not problems, '\n'.join(problems)


@pytest.mark.parametrize('path', CATALOGUES, ids=named)
def test_the_compiled_catalogue_says_what_the_source_says(path: Path) -> None:
    with path.with_suffix('.mo').open('rb') as compiled:
        catalogue = gettext.GNUTranslations(compiled)

    stale = []

    for entry in entries(path):
        if entry.msgid_plural:
            said = [catalogue.ngettext(entry.msgid, entry.msgid_plural, n) for n in (1, 2)]
            meant = [entry.msgstr[0], entry.msgstr[1]]
        else:
            said, meant = [catalogue.gettext(entry.msgid)], [entry.msgstr[0]]

        if said != meant:
            stale.append(entry.msgid)

    assert not stale, f'compile the catalogue again: {stale}'


@pytest.mark.django_db
def test_the_access_pages_read_in_persian(client: Client, make_user: MakeUser) -> None:
    person = make_user(superuser=True)
    person.is_staff = True
    person.save()
    client.force_login(person)

    with override_settings(LANGUAGE_CODE='fa'):
        page = client.get('/admin/access/bundles/')

    assert BUNDLES_FA in page.content.decode()
    with translation.override('fa'):
        assert _('What it is for') == WHAT_FOR_FA, "an optional app's own catalogue is read too"

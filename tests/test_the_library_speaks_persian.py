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
PLACEHOLDER = re.compile(r'%\((\w+)\)[sdr]')

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


# ---------------------------------------------------------------------- the access pages


#: "Can create access", "Can change the ceilings of roles" and "is one of", in Persian -
#: written as escapes: the code is English only.
CREATE_ACCESS_FA = (
    '\u0645\u06cc\u200c\u062a\u0648\u0627\u0646\u062f \u062f\u0633'
    '\u062a\u0631\u0633\u06cc \u0628\u0633\u0627\u0632\u062f'
)
CEILINGS_FA = (
    '\u0645\u06cc\u200c\u062a\u0648\u0627\u0646\u062f \u0633\u0642'
    '\u0641 \u0646\u0642\u0634\u200c\u0647\u0627 \u0631\u0627 \u062a'
    '\u063a\u06cc\u06cc\u0631 \u062f\u0647\u062f'
)
IS_ONE_OF_FA = '\u06cc\u06a9\u06cc \u0627\u0633\u062a \u0627\u0632'


@pytest.mark.django_db
def test_the_librarys_own_permissions_and_apps_read_in_persian() -> None:
    """They were kept in a plain tuple, which lost the labels they are read by."""
    from django.apps import apps

    from clearance.labels import labels_in
    from tests.conftest import permission

    persian = labels_in('fa')

    assert persian.of(permission('clearance.permission_create')) == CREATE_ACCESS_FA
    assert persian.of(permission('clearance.role_ceiling_edit')) == CEILINGS_FA
    assert permission('clearance.role_ceiling_edit').name == 'Can change the ceilings of roles'
    with translation.override('fa'):
        assert str(apps.get_app_config('clearance').verbose_name) != 'Clearance'


@pytest.mark.django_db
def test_the_grid_and_the_rule_builder_say_their_words_in_persian(
    client: Client, make_user: MakeUser
) -> None:
    person = make_user(superuser=True)
    person.is_staff = True
    person.save()
    client.force_login(person)

    with override_settings(LANGUAGE_CODE='fa'):
        grid = client.get('/admin/access/bundles/add/').content.decode()
        builder = client.get('/admin/access/scopes/add/?model=lending.Loan').content.decode()

    with translation.override('fa'):
        view = _('View')
    assert view != 'View'
    assert f'<th>{view}</th>' in grid
    assert f'>{IS_ONE_OF_FA}</option>' in builder
    assert 'clearance-breadcrumbs' in grid, "the bar Django's own pages have"


def test_every_operator_of_a_rule_has_words() -> None:
    from clearance.admin.scopes import OPERATOR_WORDS
    from clearance.rules import OPERATORS

    assert set(OPERATOR_WORDS) == set(OPERATORS)

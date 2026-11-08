"""
The pages work in a real browser - the rule builder's script, and Persian,
right to left.

Run with ``nox -s browser``; the ordinary sessions leave these out. If they
fail, an administrator cannot add a condition the server would accept, a
page breaks for a browser without the script, or the access pages are laid
out left to right in a language read the other way.
"""

from collections.abc import Iterator
from typing import Any

import pytest
from django.test import Client, override_settings

from clearance.models import ScopeRule
from tests.conftest import MakeUser
from tests.project.accounts.models import Person

playwright = pytest.importorskip('playwright.sync_api')

pytestmark = [pytest.mark.browser, pytest.mark.django_db(transaction=True)]


@pytest.fixture
def administrator(make_user: MakeUser) -> Person:
    person = make_user(superuser=True)
    person.is_staff = True
    person.save()
    return person


@pytest.fixture
def browser() -> Iterator[Any]:
    with playwright.sync_playwright() as driver:
        launched = driver.chromium.launch()
        yield launched
        launched.close()


def page_for(browser: Any, live_server: Any, person: Person, **options: Any) -> Any:
    """A page signed in as ``person``, by the session cookie Django's test client makes."""
    client = Client()
    client.force_login(person)
    context = browser.new_context(**options)
    context.add_cookies(
        [{'name': 'sessionid', 'value': client.cookies['sessionid'].value, 'url': live_server.url}]
    )
    return context.new_page()


def test_conditions_are_added_and_removed_and_the_rule_is_saved(
    browser: Any, live_server: Any, administrator: Person
) -> None:
    page = page_for(browser, live_server, administrator)
    page.goto(f'{live_server.url}/admin/access/scopes/add/?model=lending.Loan')

    page.fill('#clearance-code', 'northern_large')
    page.fill('#clearance-name', 'Large, in the north')
    rows = page.locator('tr.clearance-condition')
    assert rows.count() == 3

    page.click('#clearance-add')
    assert rows.count() == 4
    rows.nth(3).locator('.clearance-remove').click()
    rows.nth(2).locator('.clearance-remove').click()
    assert rows.count() == 2

    rows.nth(0).locator('input[name="field"]').fill('amount')
    rows.nth(0).locator('select[name="operator"]').select_option('at_least')
    rows.nth(0).locator('input[name="value"]').fill('500')
    rows.nth(1).locator('input[name="field"]').fill('region')
    rows.nth(1).locator('select[name="kind"]').select_option('person')
    rows.nth(1).locator('input[name="value"]').fill('region')
    page.click('input[type="submit"][value="Save"]')
    page.wait_for_url('**/admin/access/scopes/*/')

    assert ScopeRule.objects.get(code='northern_large').conditions == [
        {'field': 'amount', 'operator': 'at_least', 'value': {'constant': '500'}},
        {'field': 'region', 'operator': 'is', 'value': {'person': 'region'}},
    ]


def test_without_the_script_the_rule_is_built_three_conditions_at_a_time(
    browser: Any, live_server: Any, administrator: Person
) -> None:
    page = page_for(browser, live_server, administrator, java_script_enabled=False)
    page.goto(f'{live_server.url}/admin/access/scopes/add/?model=lending.Loan')

    assert not page.is_visible('#clearance-add')
    page.fill('#clearance-code', 'large')
    page.fill('#clearance-name', 'Large')
    page.locator('input[name="field"]').first.fill('amount')
    page.locator('select[name="operator"]').first.select_option('at_least')
    page.locator('input[name="value"]').first.fill('500')
    page.click('input[type="submit"][value="Save"]')
    page.wait_for_url('**/admin/access/scopes/*/')

    assert ScopeRule.objects.filter(code='large').exists()


@override_settings(LANGUAGE_CODE='fa')
def test_in_persian_the_pages_read_right_to_left(
    browser: Any, live_server: Any, administrator: Person
) -> None:
    page = page_for(browser, live_server, administrator)
    page.goto(f'{live_server.url}/admin/access/bundles/add/')

    assert page.get_attribute('html', 'dir') == 'rtl'

    row = page.locator('table.clearance-grid tbody tr').first
    model = row.locator('th').bounding_box()
    first_tick = row.locator('td').first.bounding_box()
    assert model['x'] > first_tick['x'], 'the model is read first: on the right'


@pytest.mark.parametrize('language', ['en', 'fa'])
@pytest.mark.parametrize(
    'address',
    [
        '/admin/access/bundles/add/',
        '/admin/access/scopes/add/?model=lending.Loan',
        '/admin/access/fields/lending.Loan/',
        '/admin/access/actions/',
    ],
)
def test_no_page_is_wider_than_the_screen_in_either_direction(
    browser: Any, live_server: Any, administrator: Person, language: str, address: str
) -> None:
    with override_settings(LANGUAGE_CODE=language):
        page = page_for(
            browser, live_server, administrator, viewport={'width': 1280, 'height': 800}
        )
        page.goto(f'{live_server.url}{address}')

        wide, screen = page.evaluate(
            '[document.documentElement.scrollWidth, document.documentElement.clientWidth]'
        )

    assert wide <= screen, f'{address} in {language} is {wide}px on a {screen}px screen'

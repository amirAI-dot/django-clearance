"""
The source - the library, its tests and the example project - is ASCII: English, with any other
language's text in the translation catalogues, or written as escapes.

If this fails, a string in another script slipped into the code, where a
translator never sees it and a reader of the source cannot read it.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUFFIXES = ('.py', '.html', '.js', '.css', '.txt')


def test_every_source_file_is_ascii() -> None:
    found = [
        f'{path.relative_to(ROOT)}:{number}'
        for folder in ('src', 'tests', 'example')
        for path in sorted((ROOT / folder).rglob('*'))
        if path.suffix in SUFFIXES and path.is_file()
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1)
        if not line.isascii()
    ]

    assert not found, f'not ASCII: {", ".join(found)}'

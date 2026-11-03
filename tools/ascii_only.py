"""
Refuses any character outside ASCII in the project's Python files.

The code is written in English, and every message a person reads is marked
for translation; Persian lives in the translation catalogues and nowhere
else. A Persian string typed into the code instead skips the catalogue - it
reads correctly in one language and wrongly in every other - and a test
holding Persian digits is better written as escapes (``'\\u06f0'``), which say
which character was meant.

    python tools/ascii_only.py src tests

Exits non-zero, naming every offending line, when it finds one.
"""

import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    """One line holding a character outside ASCII."""

    path: Path
    line_number: int
    line: str

    def __str__(self) -> str:
        return f'{self.path}:{self.line_number}: {self.line.strip()}'


class AsciiOnlyCheck:
    """Walks the given files and directories and reports non-ASCII lines."""

    pattern = '*.py'

    def __init__(self, roots: Iterable[Path]) -> None:
        self.roots = tuple(roots)

    def files(self) -> Iterator[Path]:
        for root in self.roots:
            if root.is_file():
                yield root
            else:
                yield from sorted(root.rglob(self.pattern))

    def findings(self) -> Iterator[Finding]:
        for path in self.files():
            text = path.read_text(encoding='utf-8')

            for number, line in enumerate(text.splitlines(), start=1):
                if not line.isascii():
                    yield Finding(path, number, line)


def main(arguments: list[str]) -> int:
    findings = list(AsciiOnlyCheck(Path(argument) for argument in arguments).findings())

    for finding in findings:
        print(finding)

    if findings:
        print(f'\n{len(findings)} line(s) outside ASCII. Mark the text for translation instead.')

    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

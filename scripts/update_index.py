#!/usr/bin/env python3
"""Update only the marked solution index in README.md; Python standard library."""
from __future__ import annotations

import argparse
import html
from pathlib import Path
import re
from urllib.parse import quote, urlsplit

START = '<!-- solution-index:start -->'
END = '<!-- solution-index:end -->'


def markdown(value: str) -> str:
    value = html.escape(' '.join(value.split()), quote=False)
    return re.sub(r'([\\`*_{\[\]}()|!])', r'\\\1', value)


def source_link(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if parsed.scheme not in ('http', 'https') or not parsed.netloc:
            return '—'
    except ValueError:
        return '—'
    return '[problem](' + quote(value, safe='/:?#=&%+@;,-._~') + ')'


def make_index(root: Path) -> str:
    rows = []
    for path in sorted((root / 'solutions').rglob('*.cpp')):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root)
        if not path.resolve().is_relative_to((root / 'solutions').resolve()):
            continue
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError as error:
            raise ValueError(f'{relative} must use UTF-8 encoding') from error
        metadata = {}
        for line in text.splitlines()[:80]:
            match = re.fullmatch(r'\s*//\s*(Problem|Source|Difficulty):\s*(.*?)\s*', line, re.IGNORECASE)
            if match and match.group(2):
                metadata.setdefault(match.group(1).lower(), match.group(2))
            elif line.strip() and not line.lstrip().startswith('//'):
                break
        label = metadata.get('problem', re.sub(r'[-_]+', ' ', path.stem))
        topic = path.parent.relative_to(root / 'solutions').as_posix()
        url = quote(relative.as_posix(), safe='/')
        rows.append(f'| [{markdown(label)}]({url}) | {markdown(topic)} | {markdown(metadata.get("difficulty", "—"))} | {source_link(metadata.get("source", ""))} |')
    count = len(rows)
    content = [f'**{count} solution files** uploaded to this repository.']
    if rows:
        content += ['', '| Solution | Topic | Difficulty | Source |', '| --- | --- | --- | --- |', *rows]
    else:
        content += ['', 'No solutions uploaded yet. The folders and templates are ready for the first upload.']
    return '\n'.join(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--check', action='store_true', help='fail on a stale index without writing')
    args = parser.parse_args()
    root = args.root.resolve()
    readme = root / 'README.md'
    try:
        original = readme.read_text(encoding='utf-8')
        if original.count(START) != 1 or original.count(END) != 1 or original.index(START) >= original.index(END):
            raise ValueError('README.md requires one ordered pair of solution-index markers')
        before, remainder = original.split(START)
        _, after = remainder.split(END)
        updated = before + START + '\n' + make_index(root) + '\n' + END + after
    except (OSError, UnicodeError, ValueError) as error:
        parser.exit(2, f'Index error: {error}\n')
    if args.check and original != updated:
        parser.exit(1, 'Solution index is stale. Run python3 scripts/update_index.py\n')
    if not args.check and original != updated:
        readme.write_text(updated, encoding='utf-8')
    print('Solution index is current.' if args.check else 'Solution index updated.')


if __name__ == '__main__':
    main()

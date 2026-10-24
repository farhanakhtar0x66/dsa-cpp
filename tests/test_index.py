import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'update_index.py'


class IndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'solutions' / 'arrays').mkdir(parents=True)
        (self.root / 'README.md').write_text('Before\n<!-- solution-index:start -->\nold\n<!-- solution-index:end -->\nAfter\n')

    def run_index(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root), *args], capture_output=True, text=True)

    def readme(self):
        return (self.root / 'README.md').read_text()

    def test_empty_repository_is_honest_and_templates_are_excluded(self):
        (self.root / 'templates').mkdir()
        (self.root / 'templates' / 'solution.cpp').write_text('int main() {}')
        result = self.run_index()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('0 solution files', self.readme())
        self.assertIn('No solutions uploaded yet.', self.readme())
        self.assertTrue(self.readme().startswith('Before\n'))
        self.assertTrue(self.readme().endswith('After\n'))

    def test_metadata_and_paths_are_safe_in_markdown(self):
        (self.root / 'solutions' / 'arrays' / 'two [sum].cpp').write_text('// Problem: A | [link] <tag>\n// Difficulty: Easy\n// Source: https://example.com/a_(b)\nclass Solution {};\n')
        result = self.run_index()
        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.readme()
        self.assertIn('A \\| \\[link\\] &lt;tag&gt;', text)
        self.assertIn('solutions/arrays/two%20%5Bsum%5D.cpp', text)
        self.assertIn('https://example.com/a_%28b%29', text)
        self.assertIn('Easy', text)

    def test_fallback_title_nested_topic_and_unsafe_source(self):
        folder = self.root / 'solutions' / 'graphs' / 'traversal'
        folder.mkdir(parents=True)
        (folder / 'breadth-first.cpp').write_text('// Source: javascript:alert(1)\nclass Solution {};')
        self.assertEqual(self.run_index().returncode, 0)
        self.assertIn('breadth first', self.readme())
        self.assertIn('graphs/traversal', self.readme())
        self.assertNotIn('javascript:', self.readme())

    def test_check_detects_stale_index_without_writing(self):
        original = self.readme()
        self.assertEqual(self.run_index('--check').returncode, 1)
        self.assertEqual(self.readme(), original)
        self.assertEqual(self.run_index().returncode, 0)
        self.assertEqual(self.run_index('--check').returncode, 0)

    def test_invalid_encoding_leaves_readme_untouched(self):
        (self.root / 'solutions' / 'arrays' / 'bad.cpp').write_bytes(b'\xff')
        original = self.readme()
        result = self.run_index()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('UTF-8', result.stderr)
        self.assertEqual(self.readme(), original)

    def test_missing_markers_does_not_overwrite_document(self):
        (self.root / 'README.md').write_text('Keep me\n')
        self.assertNotEqual(self.run_index().returncode, 0)
        self.assertEqual(self.readme(), 'Keep me\n')


if __name__ == '__main__':
    unittest.main()

"""Check attribution boundaries and empty-body/Unicode Git history parsing."""
import importlib.util
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/export_contributions.py'
spec = importlib.util.spec_from_file_location('export_contributions', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ContributionExportTests(unittest.TestCase):
    def test_empty_body_and_unicode_title_are_retained(self):
        fields = ['a'*40, '2026-11-18T10:23:34+08:00', '2026-11-18T10:23:34+08:00',
                  'ZHONGJUNHAN', '1230037310 钟峻瀚: 修复入口', '']
        records = module.parse_log('\x1f'.join(fields)+'\x1e\n', '1230037310')
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['subject'], fields[4])
        self.assertEqual(records[0]['body'], '')

    def test_body_identity_allowed_but_other_or_partial_id_excluded(self):
        def record(title, body):
            return '\x1f'.join(['b'*40, 'date', 'date', 'author', title, body])+'\x1e\n'
        raw = record('Team update', '1230037310 Zhong Junhan\n')
        raw += record('1230036051 GUO HAOXUAN: update', '')
        raw += record('912300373100 is not the target ID', '')
        records = module.parse_log(raw, '1230037310')
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['body'], '1230037310 Zhong Junhan')


if __name__ == '__main__':
    unittest.main()

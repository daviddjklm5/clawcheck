import tempfile
import unittest
from pathlib import Path

from automation.scripts.check_text_encoding import scan_file


class TextEncodingGuardTest(unittest.TestCase):
    def test_scan_file_reports_replacement_character(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "sample.py"
            path.write_text('value = "\\u574f\\ufffd\\u5b57"\n'.encode("utf-8").decode("unicode_escape"), encoding="utf-8")

            findings = scan_file(path, root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].reason, "replacement character found")
        self.assertEqual(findings[0].line, 1)

    def test_scan_file_reports_mojibake(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "sample.py"
            path.write_text('headers = ["\\u9422\\u5ba0\\ue1ec\\u7eeb\\u8bf2\\u7037"]\n'.encode("utf-8").decode("unicode_escape"), encoding="utf-8")

            findings = scan_file(path, root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].reason, "possible GBK/GB18030 mojibake")
        self.assertEqual(findings[0].recovered, 'headers = ["申请类型"]')

    def test_scan_file_reports_non_utf8_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            path = root / "sample.sql"
            path.write_bytes("申请类型".encode("gbk"))

            findings = scan_file(path, root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].reason, "non-UTF-8 text file")


if __name__ == "__main__":
    unittest.main()

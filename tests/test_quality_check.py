from pathlib import Path
import tempfile
import unittest
from tools.quality_check import summarize


class QualityReportTests(unittest.TestCase):
    def test_failure_and_skip_are_distinct(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "report.xml"
            p.write_text('<testsuites><testsuite><testcase name="ok"/><testcase name="bad"><failure/></testcase><testcase name="skip"><skipped/></testcase></testsuite></testsuites>', encoding="utf-8")
            result = summarize(p, 1)
            self.assertEqual((result["total"], result["passed"], result["failed_or_error"], result["skipped"]), (3, 1, 1, 1))
            self.assertFalse(result["approved"])
            self.assertTrue(result["partial_coverage"])

    def test_empty_and_nonzero_never_approve(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "report.xml"
            p.write_text("<testsuites/>", encoding="utf-8")
            self.assertFalse(summarize(p, 0)["approved"])
            p.write_text('<testsuite><testcase name="ok"/></testsuite>', encoding="utf-8")
            self.assertFalse(summarize(p, 2)["approved"])
            self.assertTrue(summarize(p, 0)["approved"])

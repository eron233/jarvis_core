"""Execute a suite real e resuma falhas sem despejar logs no agente."""
from pathlib import Path
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def summarize(report: Path, exit_code: int) -> dict:
    root = ET.parse(report).getroot()
    cases = list(root.iter("testcase"))
    failures = []
    skipped = 0
    for case in cases:
        if case.find("failure") is not None or case.find("error") is not None:
            failures.append({"class": case.get("classname"), "test": case.get("name")})
        elif case.find("skipped") is not None:
            skipped += 1
    passed = len(cases) - len(failures) - skipped
    return {"exit_code": exit_code, "total": len(cases), "passed": passed,
            "failed_or_error": len(failures), "skipped": skipped,
            "failures": failures,
            "approved": exit_code == 0 and passed > 0 and not failures,
            "partial_coverage": skipped > 0}


def main() -> int:
    output = Path(tempfile.mkdtemp(prefix="iris-quality-"))
    report = output / "junit.xml"
    log = output / "pytest.log"
    with log.open("wb") as stream:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "--tb=short", "--junitxml", str(report)],
            cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=False,
        )
    try:
        summary = summarize(report, result.returncode)
    except (OSError, ET.ParseError):
        summary = {"exit_code": result.returncode, "approved": False,
                   "error": "Relatorio de testes ausente ou invalido"}
    summary["local_log"] = str(log)
    summary["local_report"] = str(report)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return result.returncode or (0 if summary["approved"] else 1)


if __name__ == "__main__":
    raise SystemExit(main())

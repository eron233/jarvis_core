"""Execute a suite real e resuma falhas sem despejar logs no agente."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def summarize(report: Path, exit_code: int) -> dict:
    root = ET.parse(report).getroot()
    if root.tag not in {"testsuite", "testsuites"}:
        raise ValueError("Formato JUnit invalido")
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
            "failures": failures[:100],
            "failures_omitted": max(0, len(failures) - 100),
            "approved": exit_code == 0 and passed > 0 and not failures,
            "release_ready": exit_code == 0 and passed > 0 and not failures and skipped == 0,
            "partial_coverage": skipped > 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--allow-skips", action="store_true", help="Apenas verificacao parcial, nao libera publicacao.")
    args = parser.parse_args()
    if not 1 <= args.timeout <= 14400:
        parser.error("timeout deve estar entre 1 e 14400 segundos")
    output = Path(tempfile.mkdtemp(prefix="iris-quality-"))
    report = output / "junit.xml"
    log = output / "pytest.log"
    try:
        with log.open("wb") as stream:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "--tb=short", "--junitxml", str(report)],
                cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=False, timeout=args.timeout,
            )
        try:
            summary = summarize(report, result.returncode)
        except (OSError, ET.ParseError, ValueError):
            summary = {"exit_code": result.returncode, "approved": False, "release_ready": False,
                       "error": "Relatorio de testes ausente ou invalido"}
    except subprocess.TimeoutExpired:
        summary = {"exit_code": 124, "approved": False, "release_ready": False, "error": "Tempo de testes excedido"}
    except OSError:
        summary = {"exit_code": 1, "approved": False, "release_ready": False, "error": "Nao foi possivel iniciar pytest"}
    summary["local_log"] = str(log)
    summary["local_report"] = str(report)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary["exit_code"] or (0 if (summary["approved"] if args.allow_skips else summary["release_ready"]) else 1)


if __name__ == "__main__":
    raise SystemExit(main())

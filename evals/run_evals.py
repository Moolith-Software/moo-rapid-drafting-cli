"""Run the golden dataset through the task, then score it.

    python run_evals.py

Writes results.json next to this file and prints a summary table.
"""

import json
from pathlib import Path

from checks import run_checks
from judge import judge
from task import run

HERE = Path(__file__).parent
GREEN, RED, DIM, RESET = "\033[32m", "\033[31m", "\033[2m", "\033[0m"


def main():
    dataset = json.loads((HERE / "dataset.json").read_text())
    results = []

    for case in dataset:
        print(f"{DIM}running {case['id']}...{RESET}")
        output = run(case["input"])
        checks = run_checks(output, case["expected"])
        verdict = judge(case["input"], output.get("reply", ""))

        results.append(
            {
                "id": case["id"],
                "output": output,
                "checks": checks,
                "judge": verdict,
                "passed": all(c["passed"] for c in checks) and verdict["passed"],
            }
        )

    report(results)
    (HERE / "results.json").write_text(json.dumps(results, indent=2))
    print(f"\n{DIM}full output written to results.json{RESET}")

    # Non-zero exit so this can gate a commit or CI run.
    raise SystemExit(0 if all(r["passed"] for r in results) else 1)


def report(results):
    print(f"\n{'case':<24} {'checks':<10} {'judge':<8} result")
    print("-" * 56)

    for r in results:
        n_pass = sum(c["passed"] for c in r["checks"])
        n = len(r["checks"])
        mark = f"{GREEN}PASS{RESET}" if r["passed"] else f"{RED}FAIL{RESET}"
        print(f"{r['id']:<24} {n_pass}/{n:<8} {r['judge']['score']}/5{'':<4} {mark}")

        for c in r["checks"]:
            if not c["passed"]:
                print(f"{DIM}    x {c['name']}: {c['note']}{RESET}")
        if not r["judge"]["passed"]:
            print(f"{DIM}    x judge: {r['judge']['reason']}{RESET}")

    total = len(results)
    passed = sum(r["passed"] for r in results)
    scores = [r["judge"]["score"] for r in results]
    print("-" * 56)
    print(f"{passed}/{total} cases passed   avg judge score {sum(scores) / total:.1f}/5")


if __name__ == "__main__":
    main()

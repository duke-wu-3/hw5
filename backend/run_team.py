"""Run the Campus Customs team once from the command line.

    python backend/run_team.py ["optional instruction for Boss"]
"""

import asyncio
import json
import sys

from agents.team import run_team

if __name__ == "__main__":
    args = sys.argv[1:]
    report = asyncio.run(run_team(*args))
    print(json.dumps(report.model_dump(), indent=2, ensure_ascii=False))

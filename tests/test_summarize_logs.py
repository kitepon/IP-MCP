"""The ordinary summary CLI includes every retained generation, oldest first."""
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def test_summary_reads_rotated_files_in_order(tmp_path):
    path = tmp_path / "access.jsonl"
    for suffix, quota in [(".2", "30"), (".1", "20"), ("", "10")]:
        record = {"ts": datetime.now(UTC).isoformat(), "source": "jpo_official",
                  "endpoint": "/x", "outcome": "ok", "elapsed_ms": 1,
                  "remain_today": quota}
        Path(str(path) + suffix).write_text(json.dumps(record) + "\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(Path(__file__).parents[1] / "scripts/summarize_logs.py"),
         "--path", str(path)], check=True, capture_output=True, text=True,
    )
    assert "total calls:   3" in result.stdout
    assert "remain=10" in result.stdout

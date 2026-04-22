"""
Smoke test for the FastAPI backend.

Starts a uvicorn server, sends a sample journal payload to
/api/process_journals, and asserts the response structure is correct.

Usage:
    python test_api.py
"""

import requests
import sys
import time
import subprocess

SERVER_URL = "http://localhost:8000"
STARTUP_WAIT = 4  # seconds to wait for uvicorn to start


def start_server() -> subprocess.Popen:
    return subprocess.Popen(
        ["python3", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def build_payload() -> dict:
    return {
        "journals": [
            {
                "id": "1",
                "entry_number": 1,
                "created_at": "2024-05-10 08:00:00",
                "period": "Morning",
                "content": "Barely slept. Very anxious about the project deadline approaching.",
                "timestamp": "2024-05-10 08:00:00",
            },
            {
                "id": "2",
                "entry_number": 2,
                "created_at": "2024-05-10 14:00:00",
                "period": "Afternoon",
                "content": "Skipped lunch, stayed at desk all day. Feeling overwhelmed.",
                "timestamp": "2024-05-10 14:00:00",
            },
        ],
        "user_id": "test_user",
    }


def run_tests() -> bool:
    print("Sending POST /api/process_journals ...")
    response = requests.post(f"{SERVER_URL}/api/process_journals", json=build_payload(), timeout=120)

    # ── Status code ───────────────────────────────────────────────────────
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    print(f"  [OK] status_code == 200")

    data = response.json()

    # ── Top-level keys ────────────────────────────────────────────────────
    for key in ("status", "user_id", "journal_count", "journal_summary",
                "wellbeing", "recommendations", "proposed_changes", "errors"):
        assert key in data, f"Missing key in response: '{key}'"
    print(f"  [OK] all top-level keys present")

    # ── Pipeline completed ────────────────────────────────────────────────
    assert data["status"] in ("completed", "completed_with_warnings"), \
        f"Unexpected status: {data['status']}  errors={data.get('errors')}"
    print(f"  [OK] status == '{data['status']}'")

    # ── User ID echoed back ───────────────────────────────────────────────
    assert data["user_id"] == "test_user", f"user_id mismatch: {data['user_id']}"
    print(f"  [OK] user_id echoed correctly")

    # ── Journal count ─────────────────────────────────────────────────────
    assert data["journal_count"] == 2, f"Expected journal_count=2, got {data['journal_count']}"
    print(f"  [OK] journal_count == 2")

    # ── Wellbeing shape ───────────────────────────────────────────────────
    wb = data.get("wellbeing") or {}
    assert wb.get("risk_level") in ("minimal", "mild", "moderate", "severe"), \
        f"Unexpected risk_level: {wb.get('risk_level')}"
    assert isinstance(wb.get("key_concerns"), list), "key_concerns should be a list"
    assert isinstance(wb.get("positive_indicators"), list), "positive_indicators should be a list"
    print(f"  [OK] wellbeing shape valid  (risk={wb['risk_level']})")

    # ── Recommendations ───────────────────────────────────────────────────
    assert isinstance(data["recommendations"], list), "recommendations should be a list"
    print(f"  [OK] recommendations is a list  ({len(data['recommendations'])} items)")

    # ── Proposed changes ─────────────────────────────────────────────────
    assert isinstance(data["proposed_changes"], list), "proposed_changes should be a list"
    print(f"  [OK] proposed_changes is a list  ({len(data['proposed_changes'])} items)")

    # ── Duration (bonus, not always present) ─────────────────────────────
    if "duration_seconds" in data:
        assert isinstance(data["duration_seconds"], (int, float)), "duration_seconds should be numeric"
        print(f"  [OK] duration_seconds == {data['duration_seconds']:.1f}s")

    return True


def main():
    server = start_server()
    time.sleep(STARTUP_WAIT)
    try:
        passed = run_tests()
        if passed:
            print("\nAll assertions passed.")
    except AssertionError as e:
        print(f"\nASSERTION FAILED: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        server.terminate()
        server.wait()


if __name__ == "__main__":
    main()

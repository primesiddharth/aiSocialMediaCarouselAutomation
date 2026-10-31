"""
Phase 5 Verification Suite
Validates 02_drip_feed_publisher.json structure, Cron schedule (8AM, 12PM, 4PM),
3-row batch limit, Instagram text-only exclusion rule, and atomic status commit.
"""
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\zero-touch-social-automation")
WORKFLOW_B = ROOT / "workflows" / "02_drip_feed_publisher.json"

REQUIRED_NODES = [
    "01_Drip_Feed_Cron_Trigger",
    "02_Fetch_Sheet_Rows",
    "03_Filter_Approved_Batch_Max_3",
    "04_Lock_Row_Publishing",
    "05_Publish_To_Buffer_Channels",
    "06_Commit_Published_Status_To_Sheet",
]

def main() -> None:
    print("🔍 Running Phase 5 Drip-Feed Publisher Verification Suite...\n")
    errors: list[str] = []

    if not WORKFLOW_B.exists():
        print(f"❌ [FAIL] Missing {WORKFLOW_B}")
        sys.exit(1)

    try:
        wf = json.loads(WORKFLOW_B.read_text(encoding="utf-8"))
        print(f"  [PASS] Loaded valid JSON: {WORKFLOW_B.relative_to(ROOT)}")

        nodes = {n.get("name"): n for n in wf.get("nodes", [])}
        for req in REQUIRED_NODES:
            if req in nodes:
                print(f"  [PASS] Verified Node: {req}")
            else:
                errors.append(f"Missing required node: {req}")

        # 1. Verify Cron Trigger uses 0 8,12,16 * * *
        cron_expr = str(nodes.get("01_Drip_Feed_Cron_Trigger", {}).get("parameters", {}))
        if "0 8,12,16 * * *" in cron_expr:
            print("  [PASS] Cron schedule defaults to 8:00 AM, 12:00 PM, 4:00 PM ('0 8,12,16 * * *')")
        else:
            errors.append("Cron trigger missing '0 8,12,16 * * *' schedule.")

        # 2. Verify Batch Limit = 3 & Instagram Exclusion in Node 03
        filter_code = nodes.get("03_Filter_Approved_Batch_Max_3", {}).get("parameters", {}).get("jsCode", "")
        if "DRIP_FEED_MAX_BATCH_SIZE || '3'" in filter_code and "status === 'Approved'" in filter_code:
            print("  [PASS] Node 03 enforces strict 'Approved' gate and max 3 rows per batch")
        else:
            errors.append("Node 03 missing 'Approved' gate or 3-row batch limit.")

        if "['linkedin', 'facebook', 'instagram']" in filter_code and "['linkedin', 'facebook']" in filter_code:
            print("  [PASS] Node 03 automatically excludes Instagram when Include Image? == 'No'")
        else:
            errors.append("Node 03 missing Instagram exclusion logic for text-only posts.")

        # 3. Verify Atomic Published status commit in Node 05 & 06
        pub_code = nodes.get("05_Publish_To_Buffer_Channels", {}).get("parameters", {}).get("jsCode", "")
        if "allSucceeded ? 'Published' : 'Approved'" in pub_code:
            print("  [PASS] Node 05 safeguards against marking posts 'Published' before successful submission")
        else:
            errors.append("Node 05 missing atomic Published/Approved rollback safeguard.")

    except Exception as exc:
        errors.append(f"JSON parsing error: {exc}")

    print("\n" + "=" * 65)
    if errors:
        print("❌ PHASE 5 VERIFICATION FAILED:")
        for e in errors:
            print(f"   - {e}")
        sys.exit(1)
    else:
        print("✅ ALL PHASE 5 DRIP-FEED & APPROVAL GATE CHECKS PASSED!")

if __name__ == "__main__":
    main()
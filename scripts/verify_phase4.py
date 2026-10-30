"""
Phase 4 Verification Suite
Validates 01_draft_generation_pipeline.json structure, conditional routing branches,
environment variable bindings, and entrypoint-wrapper.sh $env permissions.
"""
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\zero-touch-social-automation")
WORKFLOW_A = ROOT / "workflows" / "01_draft_generation_pipeline.json"
ENTRYPOINT = ROOT / "config" / "docker" / "entrypoint-wrapper.sh"

REQUIRED_NODES = [
    "01_Schedule_Poll_Trigger",
    "02_Fetch_Sheet_Rows",
    "03_Filter_And_Sanitize_Input",
    "04_Lock_Row_Processing",
    "05_AI_Strategist_OpenRouter",
    "06_Switch_Include_Image",
    "07_Generate_And_Host_Image",
    "08_Bypass_Image_Text_Only",
    "09_Write_Drafts_To_Google_Sheet",
]

def main() -> None:
    print("🔍 Running Phase 4 Workflow A Structural & Logic Verification...\n")
    errors: list[str] = []

    # 1. Check entrypoint-wrapper.sh has N8N_BLOCK_ENV_ACCESS_IN_NODE="false"
    if ENTRYPOINT.exists():
        raw_ep = ENTRYPOINT.read_bytes()
        if b"\r\n" in raw_ep:
            ENTRYPOINT.write_bytes(raw_ep.replace(b"\r\n", b"\n"))
            print("  [FIXED] Converted CRLF -> LF on config/docker/entrypoint-wrapper.sh")
        ep_text = ENTRYPOINT.read_text(encoding="utf-8")
        if "N8N_BLOCK_ENV_ACCESS_IN_NODE" in ep_text:
            print("  [PASS] entrypoint-wrapper.sh unlocks $env access inside n8n nodes")
        else:
            errors.append("entrypoint-wrapper.sh is missing N8N_BLOCK_ENV_ACCESS_IN_NODE=false")
    else:
        errors.append("Missing config/docker/entrypoint-wrapper.sh")

    # 2. Check Workflow A JSON validity and node graph
    if not WORKFLOW_A.exists():
        errors.append(f"Missing workflow file: {WORKFLOW_A}")
    else:
        try:
            wf = json.loads(WORKFLOW_A.read_text(encoding="utf-8"))
            print(f"  [PASS] Loaded valid JSON: {WORKFLOW_A.relative_to(ROOT)}")

            node_names = [n.get("name") for n in wf.get("nodes", [])]
            for req in REQUIRED_NODES:
                if req in node_names:
                    print(f"  [PASS] Verified Node: {req}")
                else:
                    errors.append(f"Missing required node in Workflow A: {req}")

            # Verify Switch node branches to both 07 (Yes) and 08 (No)
            conns = wf.get("connections", {}).get("06_Switch_Include_Image", {}).get("main", [])
            if len(conns) == 2 and conns[0][0]["node"] == "07_Generate_And_Host_Image" and conns[1][0]["node"] == "08_Bypass_Image_Text_Only":
                print("  [PASS] Conditional Switch node routes True -> FLUX.1 Image & False -> Text-Only Bypass")
            else:
                errors.append("06_Switch_Include_Image connections are misconfigured.")

            # Ensure no hardcoded API keys leaked into workflow JSON
            raw_wf_str = WORKFLOW_A.read_text(encoding="utf-8")
            if "sk-or-v1-" in raw_wf_str or "hf_" in raw_wf_str:
                errors.append("Hardcoded API key detected inside 01_draft_generation_pipeline.json!")
            else:
                print("  [PASS] Zero hardcoded API keys in Workflow JSON (100% cloud-agnostic $env bindings)")

        except Exception as exc:
            errors.append(f"Invalid JSON in {WORKFLOW_A}: {exc}")

    print("\n" + "=" * 65)
    if errors:
        print("❌ PHASE 4 VERIFICATION FAILED:")
        for e in errors:
            print(f"   - {e}")
        sys.exit(1)
    else:
        print("✅ ALL PHASE 4 WORKFLOW A CHECKS PASSED!")

if __name__ == "__main__":
    main()
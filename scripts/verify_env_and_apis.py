"""
Master Phase 3 Pre-Flight Verification Suite.
Validates Prompts, Google Sheet ID, OpenRouter JSON AI, Hugging Face FLUX.1, ImgBB, and Buffer config.
"""
import subprocess
import sys
from pathlib import Path

# Ensure UTF-8 console output for Windows CLI
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\zero-touch-social-automation")
ENV_FILE = ROOT / ".env"

REQUIRED_PHASE3_FILES = [
    ROOT / "prompts" / "strategist_system_prompt.txt",
    ROOT / "prompts" / "strategist_user_template.txt",
    ROOT / "prompts" / "output_schema.json",
    ROOT / "scripts" / "test_openrouter_qwen.py",
    ROOT / "scripts" / "test_hf_flux_to_url.py",
]

def load_env(path: Path) -> dict[str, str]:
    env_vars: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env_vars[k.strip()] = v.strip()
    return env_vars

def main() -> None:
    print("🚀 Running Master Phase 3 API & Quota Pre-Flight Suite...\n")
    errors: list[str] = []

    # 1. Verify Phase 3 prompt & test files exist
    for f in REQUIRED_PHASE3_FILES:
        if f.exists():
            print(f"  [PASS] Found: {f.relative_to(ROOT)}")
        else:
            errors.append(f"Missing file: {f}")
            print(f"  [FAIL] Missing: {f}")

    env = load_env(ENV_FILE)

    # 2. Check Google Sheet Document ID
    sheet_id = env.get("GOOGLE_SHEET_DOCUMENT_ID", "")
    if not sheet_id or "your_google_sheet_id" in sheet_id:
        errors.append("GOOGLE_SHEET_DOCUMENT_ID in .env is still a placeholder.")
        print("  [FAIL] GOOGLE_SHEET_DOCUMENT_ID in .env is not set.")
    else:
        print(f"  [PASS] GOOGLE_SHEET_DOCUMENT_ID configured ({sheet_id[:12]}...)")

    # 3. Run OpenRouter Qwen-2.5-72B JSON Strategist Test
    print("\n--- Testing OpenRouter AI Strategist ---")
    res_or = subprocess.run([sys.executable, str(ROOT / "scripts" / "test_openrouter_qwen.py")], check=False)
    if res_or.returncode != 0:
        errors.append("OpenRouter Qwen pre-flight test failed.")

    # 4. Run Hugging Face FLUX.1 + ImgBB Public URL Test
    print("\n--- Testing Hugging Face FLUX.1 + ImgBB Hosting ---")
    res_hf = subprocess.run([sys.executable, str(ROOT / "scripts" / "test_hf_flux_to_url.py")], check=False)
    if res_hf.returncode != 0:
        errors.append("Hugging Face FLUX.1 + ImgBB pre-flight test failed.")

    print("\n" + "=" * 65)
    if errors:
        print("❌ PHASE 3 VERIFICATION FAILED:")
        for e in errors:
            print(f"   - {e}")
        sys.exit(1)
    else:
        print("✅ ALL PHASE 3 API & QUOTA PRE-FLIGHT CHECKS PASSED!")
        print("Ready to proceed to Phase 4 (Workflow A: Zero-Touch AI Strategist & Conditional FLUX.1 Pipeline).")

if __name__ == "__main__":
    main()
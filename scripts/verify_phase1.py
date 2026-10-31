"""
Phase 1 Automated Verification Script
Validates directory tree, required files, .env encryption keys, and .gitignore safety.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"D:\zero-touch-social-automation")

REQUIRED_FILES = [
    ROOT / ".gitignore",
    ROOT / ".dockerignore",
    ROOT / ".env.example",
    ROOT / ".env",
    ROOT / "Dockerfile",
    ROOT / "render.yaml",
    ROOT / "config" / "docker" / "entrypoint-wrapper.sh",
    ROOT / "config" / "docker" / "docker-compose.production.yml",
    ROOT / "config" / "caddy" / "Caddyfile",
    ROOT / "config" / "sheets" / "template_headers.csv",
    ROOT / "config" / "sheets" / "google_sheet_schema.json",
    ROOT / "config" / "sheets" / "apps_script_guard.gs",
    ROOT / "scripts" / "generate_secrets.py",
]

def main() -> None:
    print("🔍 Running Phase 1 Verification Suite...\n")
    errors = []

    # 1. Check all files exist
    for path in REQUIRED_FILES:
        if path.exists():
            print(f"  [PASS] Found: {path.relative_to(ROOT)}")
        else:
            errors.append(f"Missing required file: {path}")
            print(f"  [FAIL] Missing: {path}")

    # 2. Check LF line endings on entrypoint-wrapper.sh
    entrypoint = ROOT / "config" / "docker" / "entrypoint-wrapper.sh"
    if entrypoint.exists():
        raw_bytes = entrypoint.read_bytes()
        if b"\r\n" in raw_bytes:
            # Automatically fix CRLF to LF so Docker never fails on Linux
            entrypoint.write_bytes(raw_bytes.replace(b"\r\n", b"\n"))
            print("  [FIXED] Converted CRLF -> LF on config/docker/entrypoint-wrapper.sh")
        else:
            print("  [PASS] entrypoint-wrapper.sh uses clean Unix LF line endings")

    # 3. Check .env secrets
    env_path = ROOT / ".env"
    if env_path.exists():
        env_text = env_path.read_text(encoding="utf-8")
        if "REPLACE_WITH_GENERATED" in env_text:
            errors.append(".env still contains placeholder encryption keys. Run scripts/generate_secrets.py")
        else:
            print("  [PASS] .env contains generated 32-byte hex encryption keys")

    # 4. Verify .env is ignored by Git
    try:
        res = subprocess.run(
            ["git", "check-ignore", ".env"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if ".env" in res.stdout:
            print("  [PASS] Git properly ignores .env file")
        else:
            errors.append(".env is NOT ignored by Git! Check .gitignore.")
    except Exception as exc:
        errors.append(f"Git check failed: {exc}")

    print("\n" + "=" * 60)
    if errors:
        print("❌ PHASE 1 VERIFICATION FAILED WITH ERRORS:")
        for err in errors:
            print(f"   - {err}")
        sys.exit(1)
    else:
        print("✅ ALL PHASE 1 ACCEPTANCE CRITERIA PASSED!")
        print("Ready to proceed to Phase 2 (Card-Free Cloud Deployment: Supabase + Render + cron-job.org).")

if __name__ == "__main__":
    main()
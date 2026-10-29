"""
Phase 2 Automated Verification & Crash-Recovery Test Suite.
Validates Supabase config, live Render.com HTTPS deployment, and /healthz endpoint.
"""
import json
import socket
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(r"D:\zero-touch-social-automation")
ENV_FILE = ROOT / ".env"

def load_env(path: Path) -> dict[str, str]:
    env_vars: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env_vars[k.strip()] = v.strip()
    return env_vars

def check_healthz(base_url: str) -> tuple[bool, str]:
    health_url = f"{base_url.rstrip('/')}/healthz"
    req = urllib.request.Request(
        health_url,
        headers={"User-Agent": "ZeroTouch-Phase2-Verifier/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read().decode("utf-8").strip()
            if resp.status == 200 and "ok" in body.lower():
                return True, f"HTTP {resp.status} -> {body}"
            return False, f"Unexpected HTTP {resp.status} -> {body}"
    except urllib.error.HTTPError as he:
        return False, f"HTTPError {he.code}: {he.reason}"
    except Exception as exc:
        return False, f"Connection error: {exc}"

def main() -> None:
    print("🔍 Running Phase 2 Cloud Deployment & Crash-Recovery Verification...\n")
    env = load_env(ENV_FILE)
    errors: list[str] = []

    # 1. Verify cron_job_org_config.json exists
    cron_cfg = ROOT / "config" / "cron" / "cron_job_org_config.json"
    if cron_cfg.exists():
        print("  [PASS] Found: config/cron/cron_job_org_config.json")
    else:
        errors.append("Missing config/cron/cron_job_org_config.json")

    # 2. Verify Supabase Pooler TCP connectivity
    db_host = env.get("DB_POSTGRESDB_HOST", "")
    db_port = int(env.get("DB_POSTGRESDB_PORT", "5432"))
    db_user = env.get("DB_POSTGRESDB_USER", "")
    if not db_host or "your_project_ref" in db_user:
        errors.append("Supabase DB credentials in .env are still placeholders.")
        print("  [FAIL] Supabase DB credentials in .env are still placeholders.")
    else:
        try:
            with socket.create_connection((db_host, db_port), timeout=10):
                print(f"  [PASS] Supabase PostgreSQL Pooler reachable at {db_host}:{db_port}")
        except Exception as exc:
            errors.append(f"Supabase DB unreachable: {exc}")
            print(f"  [FAIL] Supabase DB unreachable: {exc}")

    # 3. Verify Live Render URL & /healthz endpoint
    n8n_host = env.get("N8N_HOST", "")
    webhook_url = env.get("WEBHOOK_URL", "")
    if not n8n_host or not webhook_url.startswith("https://"):
        errors.append("N8N_HOST or WEBHOOK_URL in .env is invalid.")
    else:
        print(f"  [INFO] Probing live Render instance at {webhook_url.rstrip('/')}/healthz ...")
        ok, detail = check_healthz(webhook_url)
        if ok:
            print(f"  [PASS] Live Render n8n healthcheck succeeded ({detail})")
        else:
            errors.append(f"Render /healthz check failed: {detail}")
            print(f"  [FAIL] Render /healthz check failed: {detail}")

    print("\n" + "=" * 65)
    if errors:
        print("❌ PHASE 2 VERIFICATION FAILED:")
        for e in errors:
            print(f"   - {e}")
        sys.exit(1)
    else:
        print("✅ ALL PHASE 2 CLOUD DEPLOYMENT CHECKS PASSED!")
        print("Ready to proceed to Phase 3 (API Credentials, Quotas & Pre-Flight Tests).")

if __name__ == "__main__":
    main()
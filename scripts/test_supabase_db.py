"""
Pre-flight verification for Supabase PostgreSQL Session Pooler connectivity.
"""
import socket
import ssl
import sys
from pathlib import Path

ROOT = Path(r"D:\zero-touch-social-automation")
ENV_FILE = ROOT / ".env"

def load_env(path: Path) -> dict[str, str]:
    env_vars: dict[str, str] = {}
    if not path.exists():
        return env_vars
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env_vars[k.strip()] = v.strip()
    return env_vars

def main() -> None:
    print("🔍 Testing Supabase PostgreSQL Connectivity from .env...\n")
    env = load_env(ENV_FILE)

    host = env.get("DB_POSTGRESDB_HOST", "")
    port = int(env.get("DB_POSTGRESDB_PORT", "5432"))
    user = env.get("DB_POSTGRESDB_USER", "")
    password = env.get("DB_POSTGRESDB_PASSWORD", "")

    if not host or "your_project_ref" in user or "your_supabase_password" in password:
        print("❌ [FAIL] You have not updated DB_POSTGRESDB_HOST, USER, or PASSWORD in .env yet!")
        print("   Complete Step 2 below first, update D:\\zero-touch-social-automation\\.env, and re-run.")
        sys.exit(1)

    print(f"  Target Host : {host}")
    print(f"  Target Port : {port}")
    print(f"  Target User : {user}")

    try:
        with socket.create_connection((host, port), timeout=10) as sock:
            print(f"✅ [PASS] TCP Socket connection to {host}:{port} succeeded!")
    except Exception as exc:
        print(f"❌ [FAIL] Could not connect to {host}:{port} -> {exc}")
        sys.exit(1)

if __name__ == "__main__":
    main()
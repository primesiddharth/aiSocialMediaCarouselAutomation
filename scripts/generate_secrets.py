"""
Generates cryptographically secure keys and initializes the local .env file.
"""
import secrets
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = ROOT_DIR / ".env.example"
ENV_FILE = ROOT_DIR / ".env"

def main() -> None:
    if not ENV_EXAMPLE.exists():
        raise FileNotFoundError(f"Missing {ENV_EXAMPLE}")

    content = ENV_EXAMPLE.read_text(encoding="utf-8")
    enc_key = secrets.token_hex(32)
    jwt_secret = secrets.token_hex(32)

    content = content.replace("REPLACE_WITH_GENERATED_32_BYTE_HEX_KEY", enc_key)
    content = content.replace("REPLACE_WITH_GENERATED_32_BYTE_HEX_SECRET", jwt_secret)

    if not ENV_FILE.exists():
        ENV_FILE.write_text(content, encoding="utf-8")
        print(f"✅ Created {ENV_FILE} with newly generated cryptographic keys.")
    else:
        print(f"ℹ️  {ENV_FILE} already exists. Skipping overwrite to protect existing keys.")

    print("\n🔐 Save these keys securely (you will also paste them into Render in Phase 2):")
    print(f"N8N_ENCRYPTION_KEY={enc_key}")
    print(f"N8N_USER_MANAGEMENT_JWT_SECRET={jwt_secret}")

if __name__ == "__main__":
    main()
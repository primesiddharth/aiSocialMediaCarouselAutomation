"""
Standalone Pre-Flight Test for Cloudflare Workers AI (@cf/black-forest-labs/flux-1-schnell)
+ Zero-Cost Permanent URL Hosting (ImgBB).
Capable of ~65-90 high-res FLUX.1 images per 24 hours on the 10,000 free daily neurons tier.
"""
import base64
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\zero-touch-social-automation")
ENV_FILE = ROOT / ".env"
MEDIA_DIR = ROOT / "media_storage"

def load_env(path: Path) -> dict[str, str]:
    env_vars: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env_vars[k.strip()] = re.sub(r"[<>\"'\s]", "", v.strip())
    return env_vars

def generate_cf_flux(account_id: str, api_token: str, prompt: str) -> tuple[str, bytes]:
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    payload = json.dumps({
        "prompt": prompt,
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        b64_img = data.get("result", {}).get("image")
        if not b64_img:
            raise RuntimeError(f"Cloudflare response missing base64 image: {data}")
        return b64_img, base64.b64decode(b64_img)

def upload_to_imgbb(imgbb_key: str, b64_image: str) -> str:
    form_data = urllib.parse.urlencode({
        "key": imgbb_key,
        "image": b64_image,
        "name": f"cf_flux_{int(time.time())}",
    }).encode("utf-8")
    req = urllib.request.Request("https://api.imgbb.com/1/upload", data=form_data, method="POST")
    with urllib.request.urlopen(req, timeout=45) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        return result["data"]["url"]

def main() -> None:
    print("⚡ Testing Cloudflare Workers AI (FLUX.1-schnell) + ImgBB Hosting...\n")
    env = load_env(ENV_FILE)
    cf_account = env.get("CLOUDFLARE_ACCOUNT_ID", "")
    cf_token = env.get("CLOUDFLARE_API_TOKEN", "")
    imgbb_key = env.get("IMGBB_API_KEY", "")

    if not cf_account or "paste_your" in cf_account or not cf_token or "paste_your" in cf_token:
        print("❌ [FAIL] Please set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in .env first!")
        sys.exit(1)

    prompt = (
        "Photorealistic 4k wide-angle shot of a modern enterprise AI data center dashboard "
        "displaying glowing cyan real-time telemetry charts in a sleek glass office, cinematic lighting"
    )

    print("  -> Calling Cloudflare Workers AI (@cf/black-forest-labs/flux-1-schnell)...")
    try:
        b64_img, img_bytes = generate_cf_flux(cf_account, cf_token, prompt)
    except urllib.error.HTTPError as he:
        err = he.read().decode("utf-8", errors="ignore")
        print(f"❌ [FAIL] Cloudflare HTTP {he.code}: {err}")
        sys.exit(1)
    except Exception as exc:
        print(f"❌ [FAIL] Cloudflare request failed: {exc}")
        sys.exit(1)

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    local_path = MEDIA_DIR / "test_cf_flux_output.jpg"
    local_path.write_bytes(img_bytes)
    print(f"✅ [PASS] Generated genuine FLUX.1 image ({len(img_bytes):,} bytes) -> {local_path.relative_to(ROOT)}")

    print("  -> Uploading FLUX.1 image to ImgBB...")
    public_url = upload_to_imgbb(imgbb_key, b64_img)
    print(f"✅ [PASS] Live Public URL: {public_url}")

if __name__ == "__main__":
    main()
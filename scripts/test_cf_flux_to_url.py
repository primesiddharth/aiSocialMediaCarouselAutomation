"""
Cloudflare Workers AI (@cf/black-forest-labs/flux-1-schnell) Poster Test + Auth Diagnostic.
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
        v = v.split(" #")[0].strip()  # Strip inline comments
        env_vars[k.strip()] = re.sub(r"[<>\"'\s]", "", v)
    return env_vars

def generate_cf_flux_poster(account_id: str, api_token: str, prompt: str) -> tuple[str, bytes]:
    url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/black-forest-labs/flux-1-schnell"
    req = urllib.request.Request(
        url,
        data=json.dumps({"prompt": prompt}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "User-Agent": "ZeroTouch-CF-Client/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            b64_img = data.get("result", {}).get("image")
            if not b64_img:
                raise RuntimeError(f"Missing image in response: {data}")
            return b64_img, base64.b64decode(b64_img)
    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Cloudflare HTTP {he.code}: {err_body}") from he

def upload_to_imgbb(imgbb_key: str, b64_image: str) -> str:
    form_data = urllib.parse.urlencode({
        "key": imgbb_key,
        "image": b64_image,
        "name": f"cf_poster_{int(time.time())}",
    }).encode("utf-8")
    req = urllib.request.Request("https://api.imgbb.com/1/upload", data=form_data, method="POST")
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))["data"]["url"]

def main() -> None:
    env = load_env(ENV_FILE)
    cf_account = env.get("CLOUDFLARE_ACCOUNT_ID") or env.get("CF_ACCOUNT_ID") or ""
    cf_token = env.get("CLOUDFLARE_API_TOKEN") or env.get("CLOUDFLARE_API_KEY") or env.get("CF_API_TOKEN") or ""
    imgbb_key = env.get("IMGBB_API_KEY", "")

    print(f"🔑 Loaded Account ID: {cf_account[:6]}...{cf_account[-4:] if len(cf_account) > 10 else 'INVALID'} (len={len(cf_account)})")
    print(f"🔑 Loaded API Token : {cf_token[:6]}...{cf_token[-4:] if len(cf_token) > 10 else 'INVALID'} (len={len(cf_token)})\n")

    if len(cf_account) != 32 or "paste" in cf_account.lower() or len(cf_token) < 20 or "paste" in cf_token.lower():
        print("❌ [FAIL] Your local .env still has placeholder or invalid Cloudflare credentials!")
        print("   Copy the exact CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN from Render into D:\\zero-touch-social-automation\\.env")
        sys.exit(1)

    poster_prompt = (
        'Split-layout corporate recruitment announcement poster graphic design. '
        'Left panel on navy blue gradient: bold white and yellow headline text "Welcome Our New HR!" '
        'and subtitle "RAHUL ROY" with yellow brush underline, three white circular icon badges labeled '
        '"People First", "New Ideas", "Stronger Together", and bottom yellow banner reading "Welcome Aboard!". '
        'Right side: modern office desk with black leather chair, hanging lanyard ID card reading "HR", '
        'laptop, and coffee mug. Crisp vector typography, Canva Pro poster layout, 4k.'
    )

    try:
        b64_img, img_bytes = generate_cf_flux_poster(cf_account, cf_token, poster_prompt)
    except Exception as exc:
        print(f"❌ [FAIL] {exc}")
        sys.exit(1)

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    local_path = MEDIA_DIR / "test_cf_flux_poster.jpg"
    local_path.write_bytes(img_bytes)
    print(f"✅ [PASS] Saved poster ({len(img_bytes):,} bytes) -> {local_path.relative_to(ROOT)}")
    print(f"✅ [PASS] Live Poster URL: {upload_to_imgbb(imgbb_key, b64_img)}")

if __name__ == "__main__":
    main()
"""
Cloudflare Workers AI (@cf/black-forest-labs/flux-1-schnell) Simplified Typography Test.
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
        v = v.split(" #")[0].strip()
        env_vars[k.strip()] = re.sub(r"[<>\"'\s]", "", v)
    return env_vars

def generate_cf_flux_poster(account_id: str, api_token: str, prompt: str) -> tuple[str, bytes]:
    # Switched back to flux-1-schnell for fast, JSON-compatible generation
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

    if len(cf_account) != 32 or len(cf_token) < 20:
        print("❌ [FAIL] Missing Cloudflare credentials!")
        sys.exit(1)

    # Simplified Prompt: Only 3 text elements to guarantee perfect spelling
    poster_prompt = (
        'Professional Canva-style corporate social media announcement poster, split-layout graphic design. '
        'On the left over a deep royal navy blue gradient panel: large bold modern white and vibrant yellow '
        'headline typography reading "WELCOME OUR NEW HR!" and subtitle "RAHUL ROY" with a yellow brush-stroke '
        'underline, and a warm cream brush-stroke banner reading "WELCOME ABOARD!". On the right side: a modern '
        'sunlit glass office desk with a black leather executive chair, a hanging lanyard ID card badge clearly '
        'reading "TEAM", a sleek laptop, and a white ceramic mug. Crisp vector typography, 4k resolution.'
    )

    try:
        print("  -> Generating simplified typography poster via FLUX.1-schnell...")
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
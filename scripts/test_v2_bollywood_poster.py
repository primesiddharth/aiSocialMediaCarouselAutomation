"""
Phase 1.1 V2 Bollywood Ad Poster Pre-Flight Tester
Supports:
  1. IMAGE_MODEL_PROVIDER=flux -> @cf/black-forest-labs/flux-1-schnell (Free Tier Neurons)
  2. IMAGE_MODEL_PROVIDER=qwen -> @cf/alibaba/qwen-image-3.0-pro (Strictly locked to 1024x1024 1K @ $0.04)
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
        env_vars[k.strip()] = re.sub(r"[<>\"']", "", v).strip()
    return env_vars

def build_bollywood_poster_prompt(actor: str, movie: str, dialogue: str, angle: str) -> str:
    clean_dialogue = dialogue.strip().strip('"').strip("'")
    clean_angle = angle.strip().strip('"').strip("'")
    return (
        f'Professional agency-designed social media advertising poster banner (1:1 square layout). '
        f'Cinematic Bollywood-meets-modern-tech aesthetic inspired by {movie} ({actor} vibe, stylized silhouette/graphic tribute, no copyrighted movie still). '
        f'Top-center features a glowing cinematic clapperboard and neon web-browser frame. '
        f'Dominant, ultra-crisp bold headline typography in the center reading "{clean_dialogue}" in vibrant gold and white sans-serif font. '
        f'Below the headline, a sleek dark glassmorphic callout banner with crisp white subtitle text reading "{clean_angle}". '
        f'Bottom corner features a clean modern tech badge reading "WEBSITE DESIGN". '
        f'Rich royal navy, deep crimson, and gold gradient background, vector graphic accents, Dribbble/Canva Pro agency quality, 1024x1024.'
    )

def generate_poster_dual_engine(account_id: str, api_token: str, provider: str, prompt: str) -> bytes:
    provider = provider.lower().strip()

    if provider == "qwen":
        # Cloudflare Workers AI: alibaba/qwen-image-3.0-pro (Strictly locked to 1024x1024 1K = $0.04)
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/alibaba/qwen-image-3.0-pro"
        payload = {
            "prompt": prompt,
            "size": "1024x1024",  # STRICT 1K LOCK ($0.04) - NEVER 2K
            "negative_prompt": "blurry text, misspelled words, typos, distorted letters, extra fingers, low quality, watermark",
            "watermark": False
        }
    else:
        # Default Free Tier: @cf/black-forest-labs/flux-1-schnell
        url = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/@cf/black-forest-labs/flux-1-schnell"
        payload = {
            "prompt": prompt
        }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
            "User-Agent": "ZeroTouch-V2-Engine/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            result = data.get("result", {})

            # Handle Flux output: result.image (base64)
            if isinstance(result, dict) and result.get("image"):
                return base64.b64decode(result["image"])

            # Handle Qwen Image 3.0 Pro output: result.images[0] (data:image/...;base64,... or https URI or raw base64)
            images_list = result.get("images") if isinstance(result, dict) else None
            if isinstance(images_list, list) and len(images_list) > 0:
                first_img = str(images_list[0])
                if first_img.startswith("data:image"):
                    b64_part = first_img.split(",", 1)[1]
                    return base64.b64decode(b64_part)
                elif first_img.startswith("http"):
                    with urllib.request.urlopen(first_img, timeout=30) as img_resp:
                        return img_resp.read()
                else:
                    return base64.b64decode(first_img)

            raise RuntimeError(f"Unexpected API response structure: {json.dumps(data)[:400]}")
    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Cloudflare HTTP {he.code}: {err_body}") from he

def upload_bytes_to_imgbb(imgbb_key: str, img_bytes: bytes) -> str:
    b64_str = base64.b64encode(img_bytes).decode("utf-8")
    form_data = urllib.parse.urlencode({
        "key": imgbb_key,
        "image": b64_str,
        "name": f"v2_ad_poster_{int(time.time())}",
    }).encode("utf-8")
    req = urllib.request.Request("https://api.imgbb.com/1/upload", data=form_data, method="POST")
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))["data"]["url"]

def main() -> None:
    env = load_env(ENV_FILE)
    cf_account = env.get("CLOUDFLARE_ACCOUNT_ID", "")
    cf_token = env.get("CLOUDFLARE_API_TOKEN", "")
    imgbb_key = env.get("IMGBB_API_KEY", "")
    provider = env.get("IMAGE_MODEL_PROVIDER", "flux").lower()

    # Sample Row 1 from HR's Excel Sheet
    actor = "Shah Rukh Khan"
    movie = "Om Shanti Om (2007)"
    dialogue = '"Picture abhi baaki hai mere dost"'
    angle = "Your brand's digital story hasn't even begun — let Creyotech write it"

    prompt = build_bollywood_poster_prompt(actor, movie, dialogue, angle)
    print(f"🎬 Testing V2 Bollywood Ad Poster Engine [Provider: {provider.upper()} | 1K Lock: 1024x1024]")
    print(f"📜 Verbatim Dialogue : {dialogue}")
    print(f"🎯 Verbatim Ad Angle : {angle}\n")

    img_bytes = generate_poster_dual_engine(cf_account, cf_token, provider, prompt)
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = MEDIA_DIR / f"test_v2_{provider}_poster.jpg"
    out_file.write_bytes(img_bytes)
    print(f"✅ [PASS] Saved Poster Locally ({len(img_bytes):,} bytes) -> {out_file.relative_to(ROOT)}")

    live_url = upload_bytes_to_imgbb(imgbb_key, img_bytes)
    print(f"✅ [PASS] Live Hosted Poster URL: {live_url}")

if __name__ == "__main__":
    main()
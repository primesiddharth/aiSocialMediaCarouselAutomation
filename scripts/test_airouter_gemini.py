"""
V2 Master Pre-Flight Tester: AIRouter (google/gemini-nano-banana-2.1)
Features:
  - Smart Cache: Reuses existing local PNG if present (pass --regen to generate a new image)
  - Binary Multipart/Form-Data ImgBB uploader with 3x retry (fixes SSL write timeout on 1.7MB+ PNGs)
  - Strictly faceless (zero facial features, abstract silhouettes & props only)
  - 10-way dynamic agency layout engine + Strict 1K (1024x1024) resolution
"""
import base64
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\zero-touch-social-automation")
ENV_FILE = ROOT / ".env"
MEDIA_DIR = ROOT / "media_storage"

AGENCY_LAYOUTS = [
    {
        "style": "Neo-Brutalist Swiss Typographic Grid",
        "composition": "Bold architectural grid lines, oversized high-contrast display typography anchored top-left, floating 3D matte geometric blocks, and a razor-sharp diagonal accent bar",
        "palette": "Deep obsidian black, electric cyber-gold, and crisp titanium white"
    },
    {
        "style": "Glassmorphic Split-Screen Agency Showcase",
        "composition": "Asymmetrical 60/40 diagonal split-panel layout with frosted acrylic glass cards, glowing rim-lit edges, and a floating minimalist wireframe browser window",
        "palette": "Midnight sapphire blue, neon magenta rim-lighting, and pure platinum text"
    },
    {
        "style": "Minimalist Isometric Tech-Cinema Stage",
        "composition": "Clean isometric 3D pedestal in the lower third holding symbolic vintage cinema & web UI props, surrounded by negative space for massive centered agency typography",
        "palette": "Warm charcoal grey, vibrant tangerine gold, and cream white"
    },
    {
        "style": "Retro-Futuristic Synthwave Editorial Poster",
        "composition": "Perspective laser grid floor fading into a glowing horizon ring, framed by sleek vertical editorial borders and a stacked monumental headline in the upper center",
        "palette": "Deep royal indigo, sunset crimson, and luminous chrome gold"
    },
    {
        "style": "Luxury Matte-Black & Gold Foil Monolith",
        "composition": "Central monolithic dark marble slab with embossed metallic gold-foil typography, flanked by floating abstract light ribbons and subtle bokeh particles",
        "palette": "Velvet matte black, 24k brushed gold, and warm ivory"
    },
    {
        "style": "Dynamic Bauhaus Geometric Collage",
        "composition": "Intersecting circles, sharp triangles, and clean Bauhaus color blocks framing an off-center typographic focal point and minimalist vector UI badges",
        "palette": "Deep navy, Bauhaus crimson, mustard gold, and stark off-white"
    },
    {
        "style": "Cybernetic Holographic HUD Interface",
        "composition": "Futuristic UI viewfinder brackets, subtle data-grid micro-typography in the corners, and a glowing holographic center banner showcasing the main dialogue",
        "palette": "Dark slate teal, electric cyan, and high-visibility amber gold"
    },
    {
        "style": "High-Fashion Magazine Cover Editorial",
        "composition": "Double-line luxury magazine masthead border, dramatic spotlight beams crossing an empty stage, and ultra-clean hierarchy between headline and callout pill",
        "palette": "Rich burgundy wine, champagne gold, and crisp alabaster white"
    },
    {
        "style": "Abstract Liquid-Metal & Neon Typography",
        "composition": "Flowing 3D chrome and liquid-gold abstract waves curving around a crystal-clear dark typographic safe-zone in the center",
        "palette": "Deep space violet, liquid silver chrome, and radiant solar gold"
    },
    {
        "style": "Architectural Brutalist Shadow-Play",
        "composition": "Dramatic architectural concrete arches casting long venetian-blind light shadows across a minimalist gallery wall, with bold stencil-sharp poster typography",
        "palette": "Warm espresso brown, burnt sienna, and luminous gold-leaf white"
    },
]


def load_env(path: Path) -> dict[str, str]:
    env_vars: dict[str, str] = {}
    if not path.exists():
        return env_vars
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.split(" #")[0].strip()
        env_vars[k.strip()] = re.sub(r"[<>\"'\s]", "", v)
    return env_vars


def build_dynamic_faceless_prompt(row_num: int, actor: str, movie: str, dialogue: str, angle: str) -> str:
    clean_dialogue = dialogue.strip().strip('"').strip("'")
    clean_angle = angle.strip().strip('"').strip("'")
    layout = AGENCY_LAYOUTS[(row_num - 1) % len(AGENCY_LAYOUTS)]

    return (
        f"Generate a 1024x1024 (1K resolution, 1:1 square) world-class commercial advertising agency social media poster. "
        f"Visual Art Direction: {layout['style']}. "
        f"Layout & Composition: {layout['composition']}. "
        f"Color Palette: {layout['palette']}. "
        f"Thematic Tribute: Inspired by the cinematic mood of '{movie}' ({actor} era), represented EXCLUSIVELY through iconic objects, symbolic props, abstract back-lit faceless silhouettes, and modern web-design UI elements. "
        f"STRICT NEGATIVE CONSTRAINT: ZERO human faces, NO eyes, NO noses, NO mouths, NO realistic portraits, NO facial features anywhere in the image. Keep all human references 100% faceless abstract geometric silhouettes or pure symbolic objects so text remains the undisputed hero. "
        f"EXACT TYPOGRAPHY TO RENDER ON THE POSTER (100% verbatim spelling, zero typos, ultra-sharp vector kerning): "
        f"1. Primary Hero Headline (dominant center display font): \"{clean_dialogue}\" "
        f"2. Secondary Sub-Headline (inside a sleek contrasting callout card below the headline): \"{clean_angle}\" "
        f"3. Footer Brand Pill Badge (bottom center/corner): \"WEBSITE DESIGN | CREYOTECH\""
    )


def extract_image_bytes_from_airouter(data: dict) -> bytes:
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError(f"No 'choices' in AIRouter response: {json.dumps(data)[:300]}")

    message = choices[0].get("message", {})

    def decode_candidate(val: str) -> bytes | None:
        val = val.strip()
        if val.startswith("data:image"):
            b64_part = val.split(",", 1)[1]
            return base64.b64decode(b64_part)
        if val.startswith("http://") or val.startswith("https://"):
            req = urllib.request.Request(val, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        if len(val) > 256 and re.match(r"^[A-Za-z0-9+/=\r\n]+$", val):
            return base64.b64decode(val)
        return None

    images = message.get("images") or []
    for img_item in images:
        if isinstance(img_item, str):
            res = decode_candidate(img_item)
            if res:
                return res
        elif isinstance(img_item, dict):
            nested_url = None
            if isinstance(img_item.get("image_url"), dict):
                nested_url = img_item["image_url"].get("url")
            elif isinstance(img_item.get("image_url"), str):
                nested_url = img_item["image_url"]

            for candidate in [
                nested_url,
                img_item.get("url"),
                img_item.get("b64_json"),
                img_item.get("data"),
                img_item.get("image"),
            ]:
                if isinstance(candidate, str) and candidate:
                    res = decode_candidate(candidate)
                    if res:
                        return res

    content = message.get("content")
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                nested = part.get("image_url", {})
                u = nested.get("url") if isinstance(nested, dict) else nested
                for c in [u, part.get("url"), part.get("b64_json"), part.get("text")]:
                    if isinstance(c, str) and c:
                        res = decode_candidate(c)
                        if res:
                            return res
    elif isinstance(content, str) and content:
        data_uri_match = re.search(r"(data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=]+)", content)
        if data_uri_match:
            return decode_candidate(data_uri_match.group(1))
        url_match = re.search(r"(https?://[^\s\)\"'>]+)", content)
        if url_match:
            res = decode_candidate(url_match.group(1))
            if res:
                return res

    safe_preview = json.dumps(data)[:400]
    raise RuntimeError(f"Could not extract image bytes. Response preview: {safe_preview}...")


def generate_airouter_image(api_key: str, base_url: str, model: str, prompt: str) -> bytes:
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "modalities": ["image", "text"],
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "HTTP-Referer": "https://zero-touch-n8n.onrender.com",
            "X-Title": "ZeroTouch-V2-Engine",
        },
        method="POST",
    )

    try:
        print(f"  -> Requesting {model} via AIRouter ({url})...")
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw_json = json.loads(resp.read().decode("utf-8"))
            return extract_image_bytes_from_airouter(raw_json)
    except urllib.error.HTTPError as he:
        err_body = he.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"AIRouter HTTP {he.code}: {err_body[:500]}") from he


def upload_bytes_to_imgbb(imgbb_key: str, img_bytes: bytes) -> str:
    """Uses binary multipart/form-data instead of URL-encoded base64 to prevent SSL write timeouts."""
    boundary = f"----ZeroTouchBoundary{uuid.uuid4().hex}"
    filename = f"creyotech_ad_1k_{int(time.time())}.png"

    body_parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"key\"\r\n\r\n{imgbb_key}\r\n".encode("utf-8"),
        (
            f"--{boundary}\r\n"
            f"Content-Disposition: form-data; name=\"image\"; filename=\"{filename}\"\r\n"
            f"Content-Type: image/png\r\n\r\n"
        ).encode("utf-8"),
        img_bytes,
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ]
    multipart_body = b"".join(body_parts)

    for attempt in range(1, 4):
        try:
            print(f"  -> Uploading {len(img_bytes):,} bytes to ImgBB (Attempt {attempt}/3)...")
            req = urllib.request.Request(
                "https://api.imgbb.com/1/upload",
                data=multipart_body,
                headers={
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "Content-Length": str(len(multipart_body)),
                    "User-Agent": "Mozilla/5.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=180) as resp:
                return json.loads(resp.read().decode("utf-8"))["data"]["url"]
        except Exception as err:
            if attempt == 3:
                raise RuntimeError(f"ImgBB upload failed after 3 attempts: {err}") from err
            print(f"  ⚠️ Upload timeout/retry ({err}), retrying in 3s...")
            time.sleep(3)
    raise RuntimeError("Unreachable")


def main() -> None:
    env = load_env(ENV_FILE)
    airouter_key = env.get("AIROUTER_API_KEY", "")
    airouter_base = env.get("AIROUTER_BASE_URL", "https://api.airouter.in/v1")
    model = env.get("AIROUTER_IMAGE_MODEL", "google/gemini-nano-banana-2.1")
    imgbb_key = env.get("IMGBB_API_KEY", "")

    if not airouter_key:
        print("❌ [FAIL] Missing AIROUTER_API_KEY in D:\\zero-touch-social-automation\\.env!")
        sys.exit(1)

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    out_file = MEDIA_DIR / "test_airouter_gemini_poster.png"
    force_regen = "--regen" in sys.argv

    if out_file.exists() and out_file.stat().st_size > 10000 and not force_regen:
        img_bytes = out_file.read_bytes()
        print(f"♻️ [CACHE HIT] Reusing already generated 1K poster ({len(img_bytes):,} bytes) -> {out_file.relative_to(ROOT)}")
        print("   (Tip: Pass '--regen' if you want to spend credits to generate a brand new image)")
    else:
        row_num = 1
        actor = "Shah Rukh Khan"
        movie = "Om Shanti Om (2007)"
        dialogue = "Picture abhi baaki hai mere dost"
        angle = "Your brand's digital story hasn't even begun — let Creyotech write it"

        prompt = build_dynamic_faceless_prompt(row_num, actor, movie, dialogue, angle)
        print(f"🎬 Testing AIRouter V2 Poster [Row #{row_num} | Layout: {AGENCY_LAYOUTS[0]['style']}]")
        print(f"📜 Verbatim Dialogue : \"{dialogue}\"")
        print(f"🎯 Verbatim Ad Angle : \"{angle}\"")

        try:
            img_bytes = generate_airouter_image(airouter_key, airouter_base, model, prompt)
        except Exception as exc:
            print(f"❌ [FAIL] {exc}")
            sys.exit(1)

        out_file.write_bytes(img_bytes)
        print(f"✅ [PASS] Saved 1K Poster Locally ({len(img_bytes):,} bytes) -> {out_file.relative_to(ROOT)}")

    live_url = upload_bytes_to_imgbb(imgbb_key, img_bytes)
    print(f"✅ [PASS] Live ImgBB Poster URL (Buffer Ready): {live_url}")


if __name__ == "__main__":
    main()
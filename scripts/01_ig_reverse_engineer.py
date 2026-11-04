"""
Stage 1: Instagram Design Philosophy Extractor
- Samples reference posts/Reels (or uses --local-image)
- Analyzes WHY the designs look premium via local Ollama ('llava-phi3')
- Synthesizes abstract, reusable DESIGN PRINCIPLES (hierarchy, typography craft,
  color harmony rules, spatial balance, lighting philosophy) into active_style_blueprint.json
- NEVER locks fixed objects, fixed colors, or rigid grid templates.
"""
import argparse
import base64
import io
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import cv2
import instaloader
import yt_dlp
from PIL import Image

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\zero-touch-social-automation")
ENV_FILE = ROOT / ".env"
REF_DIR = ROOT / "media_storage" / "ig_reference"
ACTIVE_BLUEPRINT_FILE = REF_DIR / "active_style_blueprint.json"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "HTTP-Referer": "https://zero-touch-n8n.onrender.com",
    "X-Title": "ZeroTouch Design Philosophy Extractor",
}


def load_env(path: Path) -> dict[str, str]:
    env_vars: dict[str, str] = {}
    if not path.exists():
        return env_vars
    for line in path.read_text(encoding="utf-8").splitlines():
        cleaned_line = line.strip()
        if not cleaned_line or cleaned_line.startswith("#") or "=" not in cleaned_line:
            continue
        k, v = cleaned_line.split("=", 1)
        v_clean = v.split(" #")[0].strip()
        env_vars[k.strip()] = re.sub(r"[<>\"'\s]", "", v_clean)
    return env_vars


def parse_ig_username(input_str: str) -> str:
    cleaned = input_str.strip().rstrip("/")
    if "instagram.com/" in cleaned:
        parts = cleaned.split("instagram.com/")[-1].split("/")
        return parts[0].split("?")[0].lstrip("@")
    return cleaned.lstrip("@")


def ensure_ollama_running() -> None:
    try:
        urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3)
        return
    except Exception:
        print("  ⚙️ Starting local Ollama server in background...")
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        for _ in range(15):
            time.sleep(1)
            try:
                urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
                return
            except Exception:
                continue


def extract_reel_keyframe_strip(video_path: Path, out_jpg: Path) -> Path:
    if out_jpg.exists() and out_jpg.stat().st_size > 1000:
        return out_jpg

    cap = cv2.VideoCapture(str(video_path))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if total_frames <= 0:
        cap.release()
        raise RuntimeError(f"Cannot read frames from {video_path.name}")

    indices = [
        max(0, int(total_frames * 0.10)),
        max(0, int(total_frames * 0.50)),
        max(0, int(total_frames * 0.85)),
    ]
    pil_frames: list[Image.Image] = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret and frame is not None:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb)
            img.thumbnail((384, 384))
            pil_frames.append(img)
    cap.release()

    if not pil_frames:
        raise RuntimeError(f"No valid frames extracted from {video_path.name}")

    w = sum(im.width for im in pil_frames)
    h = max(im.height for im in pil_frames)
    strip = Image.new("RGB", (w, h), (0, 0, 0))
    x_offset = 0
    for im in pil_frames:
        strip.paste(im, (x_offset, 0))
        x_offset += im.width

    strip.save(out_jpg, quality=85)
    return out_jpg


def load_cached_posts(target_dir: Path, limit: int) -> list[dict[str, str]]:
    if not target_dir.exists():
        return []
    shortcodes: list[str] = []
    for f in sorted(target_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.name.endswith("_strip.jpg") or f.suffix == ".json":
            continue
        code = f.stem.split("_")[0]
        if code and code not in shortcodes:
            shortcodes.append(code)

    cached: list[dict[str, str]] = []
    for code in shortcodes[:limit]:
        mp4s = sorted(target_dir.glob(f"{code}*.mp4"))
        imgs = [
            p
            for p in sorted(target_dir.glob(f"{code}*.*"))
            if p.suffix.lower() in (".jpg", ".jpeg", ".webp", ".png") and not p.name.endswith("_strip.jpg")
        ]
        is_video = len(mp4s) > 0
        analysis_img: Path | None = None

        if is_video:
            strip_path = target_dir / f"{code}_strip.jpg"
            try:
                analysis_img = extract_reel_keyframe_strip(mp4s[0], strip_path)
            except Exception:
                analysis_img = imgs[0] if imgs else None
        elif imgs:
            analysis_img = imgs[0]

        if analysis_img is not None and analysis_img.exists():
            cached.append(
                {
                    "shortcode": code,
                    "media_type": "reel_video" if is_video else "static_poster",
                    "analysis_image_path": str(analysis_img),
                }
            )
    return cached


def get_authenticated_loader(ig_user: str, ig_pass: str, target_dir: Path) -> instaloader.Instaloader:
    loader = instaloader.Instaloader(
        download_pictures=True,
        download_videos=True,
        download_video_thumbnails=True,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        dirname_pattern=str(target_dir),
        filename_pattern="{shortcode}",
    )
    if not ig_user or not ig_pass:
        return loader

    try:
        loader.load_session_from_file(ig_user)
        instaloader.Profile.from_username(loader.context, ig_user)
        print(f"     ✅ Loaded and verified existing IG session for {ig_user}")
    except Exception:
        try:
            loader.login(ig_user, ig_pass)
            loader.save_session_to_file()
        except Exception:
            pass
    return loader


def scrape_instagram_profile(
    target_username: str, limit: int, force_scrape: bool, ig_user: str, ig_pass: str
) -> list[dict[str, str]]:
    target_dir = REF_DIR / target_username
    target_dir.mkdir(parents=True, exist_ok=True)

    if not force_scrape:
        cached = load_cached_posts(target_dir, limit)
        if len(cached) >= limit:
            print(f"♻️ [STAGE 1 CACHE] Using {len(cached)} cached reference posts for @{target_username}")
            return cached

    print(f"🔍 [STAGE 1] Sampling Instagram profile @{target_username} (Limit: {limit} posts)...")
    loader = get_authenticated_loader(ig_user, ig_pass, target_dir)

    success = False
    try:
        profile = instaloader.Profile.from_username(loader.context, target_username)
        count = 0
        for post in profile.get_posts():
            if count >= limit:
                break
            try:
                loader.download_post(post, target=target_dir)
                count += 1
            except Exception:
                continue
        if count > 0:
            success = True
    except Exception as e:
        print(f"     ⚠️ Instaloader blocked ({type(e).__name__}).")

    if not success:
        print("     -> Engaging yt-dlp public extractor fallback...")
        ydl_opts = {
            "outtmpl": str(target_dir / "%(id)s.%(ext)s"),
            "playlistend": limit,
            "quiet": True,
            "writethumbnail": True,
            "no_warnings": True,
            "extract_flat": False,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([f"https://www.instagram.com/{target_username}/"])
        except Exception as ydl_err:
            cached_fallback = load_cached_posts(target_dir, limit)
            if cached_fallback:
                return cached_fallback
            print(f"     ❌ yt-dlp also blocked: {ydl_err}")
            print("     -> Use --local-image <path_to_screenshot.jpg> to bypass IP blocks.")
            sys.exit(1)

    return load_cached_posts(target_dir, limit)


def compress_image_for_vram(image_path: Path, max_dim: int = 768) -> str:
    with Image.open(image_path) as im:
        rgb = im.convert("RGB")
        rgb.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        rgb.save(buf, format="JPEG", quality=82)
        return base64.b64encode(buf.getvalue()).decode("utf-8")


def analyze_with_local_ollama(image_path: Path, model: str = "llava-phi3") -> str:
    ensure_ollama_running()
    img_b64 = compress_image_for_vram(image_path, max_dim=768)
    prompt = (
        "Analyze the underlying graphic design principles that make this visual attractive "
        "(do NOT list specific people, props, or literal colors to copy): "
        "1. Visual hierarchy & focal point strategy. "
        "2. Typography craft (scale contrast, weight balance, readability). "
        "3. Color harmony theory (how contrast and mood are achieved). "
        "4. Negative space & lighting depth."
    )

    candidate_models = [model]
    if "moondream" not in candidate_models:
        candidate_models.append("moondream")

    for cand_model in candidate_models:
        for attempt in range(1, 3):
            req = urllib.request.Request(
                "http://localhost:11434/api/chat",
                data=json.dumps(
                    {
                        "model": cand_model,
                        "messages": [{"role": "user", "content": prompt, "images": [img_b64]}],
                        "stream": False,
                        "keep_alive": "5m",
                        "options": {
                            "num_ctx": 2048,
                            "num_predict": 260,
                            "temperature": 0.2,
                        },
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=180) as resp:
                    raw_data = json.loads(resp.read().decode("utf-8"))
                    msg_obj = raw_data.get("message")
                    if not isinstance(msg_obj, dict):
                        msg_obj = {}
                    text_out = str(msg_obj.get("content") or "").strip()
                    if text_out:
                        return text_out
            except Exception as err:
                print(f"     ⚠️ Ollama ({cand_model}) attempt {attempt}/2 warning: {err}")
                time.sleep(2)

    return "Strong focal point hierarchy, high-contrast display typography, intentional negative space, and cinematic lighting depth."


def discover_free_openrouter_models(api_key: str) -> list[str]:
    priority = ["gemma-4-31b", "nemotron-3-ultra", "nemotron-3.5-super", "gemma-4-26b", "lfm2.5"]
    discovered: list[str] = []
    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={**BROWSER_HEADERS, "Authorization": f"Bearer {api_key}"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw_data = json.loads(resp.read().decode("utf-8"))
            raw_models = raw_data.get("data")
            if not isinstance(raw_models, list):
                raw_models = []
        free_ids: list[str] = []
        for m in raw_models:
            mid = str(m.get("id") or "")
            if mid.endswith(":free") and not any(
                k in mid.lower() for k in ["embed", "audio", "inkling", "safety"]
            ):
                free_ids.append(mid)
        for kw in priority:
            for fid in free_ids:
                if kw in fid.lower() and fid not in discovered:
                    discovered.append(fid)
        for fid in free_ids:
            if fid not in discovered:
                discovered.append(fid)
    except Exception:
        pass
    if "openrouter/free" not in discovered:
        discovered.append("openrouter/free")
    return discovered[:6]


def synthesize_master_style_blueprint(
    env: dict[str, str], username: str, all_vision_notes: list[str]
) -> dict[str, Any]:
    openrouter_key = str(env.get("OPENROUTER_API_KEY") or "").strip()
    joined_notes = "\n\n---\n\n".join(
        [f"Sample #{i + 1} Design Observation:\n{n}" for i, n in enumerate(all_vision_notes)]
    )

    prompt = (
        f"You are an Executive Design Philosopher analyzing reference works from @{username}.\n"
        "Extract ONLY reusable, high-level DESIGN PRINCIPLES (how the designer thinks about balance, hierarchy, "
        "typography legibility, color contrast logic, and lighting quality).\n"
        "STRICT RULES:\n"
        "1. Do NOT lock in specific colors (e.g., do not mandate 'blue neon' or 'dark background').\n"
        "2. Do NOT lock in fixed layouts (e.g., do not force '4-panel grid' or '50/50 split').\n"
        "3. Do NOT mention specific objects, props, film reels, laptops, or clapperboards.\n"
        "The goal is to teach our Creative Director HOW to design with sophistication while leaving 100% freedom "
        "to invent unique metaphors, colors, and compositions for each movie.\n\n"
        "Return ONLY valid raw JSON (no markdown blocks) with these exact keys:\n"
        "{\n"
        f'  "reference_profile": "@{username}",\n'
        '  "design_philosophy_name": "Concise title of the design philosophy",\n'
        '  "visual_hierarchy_principles": "How to establish an unmistakable hero focal point and guide the eye",\n'
        '  "typography_craft_rules": "Principles for font weight contrast, kerning, and clean separation between headline and sub-callout",\n'
        '  "color_harmony_principles": "How to balance dominant, secondary, and high-contrast accent tones",\n'
        '  "lighting_and_depth_principles": "How to use studio lighting, shadows, and negative space to create luxury depth"\n'
        "}\n\n"
        f"OBSERVATIONS:\n{joined_notes}"
    )

    for model in discover_free_openrouter_models(openrouter_key):
        print(f"  -> Distilling Design Principles via [{model}]...")
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(
                {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.4}
            ).encode("utf-8"),
            headers={**BROWSER_HEADERS, "Authorization": f"Bearer {openrouter_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
                choices = raw.get("choices")
                if not isinstance(choices, list) or not choices:
                    choices = [{}]
                first_msg = choices[0].get("message")
                if not isinstance(first_msg, dict):
                    first_msg = {}
                content = str(first_msg.get("content") or "")
                cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
                s, e = cleaned.find("{"), cleaned.rfind("}")
                if s != -1 and e != -1:
                    obj = json.loads(cleaned[s : e + 1])
                    if isinstance(obj, dict) and "visual_hierarchy_principles" in obj:
                        obj["reference_profile"] = f"@{username}"
                        obj["synthesized_by"] = model
                        return obj
        except Exception as err:
            print(f"     ⚠️ {model} skipped ({err})")
            time.sleep(1.5)

    raise RuntimeError("Failed to synthesize Master Style Blueprint.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 1: Extract Reusable Design Principles from Instagram")
    parser.add_argument("--profile", default="", help="Reference Instagram URL or @username")
    parser.add_argument("--local-image", default="", help="Path to a local image to bypass IG scraping")
    parser.add_argument("--limit", type=int, default=2, help="Number of posts to sample")
    parser.add_argument("--vision-model", default="llava-phi3", help="Local Ollama vision model")
    parser.add_argument("--force-scrape", action="store_true", help="Force fresh download from Instagram")
    args = parser.parse_args()

    env = load_env(ENV_FILE)
    posts: list[dict[str, str]] = []
    target_username = "local_reference"

    if args.local_image:
        local_path = Path(args.local_image)
        if not local_path.exists():
            print(f"❌ [FAIL] Local image not found at: {local_path}")
            sys.exit(1)
        print(f"🔍 [STAGE 1] Using local reference image: {local_path.name}")
        posts = [{"shortcode": "local_img", "media_type": "static_poster", "analysis_image_path": str(local_path)}]
        if args.profile:
            target_username = parse_ig_username(args.profile)
    elif args.profile:
        target_username = parse_ig_username(args.profile)
        ig_user = str(env.get("IG_USERNAME") or "").strip()
        ig_pass = str(env.get("IG_PASSWORD") or "").strip()
        posts = scrape_instagram_profile(target_username, args.limit, args.force_scrape, ig_user, ig_pass)
        if not posts:
            print("❌ [FAIL] No reference posts found.")
            sys.exit(1)
    else:
        print("❌ [FAIL] Provide either --profile OR --local-image.")
        sys.exit(1)

    vision_observations: list[str] = []
    for idx, item in enumerate(posts, start=1):
        print(f"🧠 [STAGE 1] Inspecting Sample #{idx} ({item['shortcode']}) with Local Ollama ({args.vision_model})...")
        notes = analyze_with_local_ollama(Path(item["analysis_image_path"]), args.vision_model)
        vision_observations.append(notes)

    print(f"\n✨ [STAGE 1] Distilling Reusable Design Principles from @{target_username}...")
    blueprint = synthesize_master_style_blueprint(env, target_username, vision_observations)

    target_dir = REF_DIR / target_username
    target_dir.mkdir(parents=True, exist_ok=True)

    profile_blueprint_path = target_dir / "master_style_blueprint.json"
    profile_blueprint_path.write_text(json.dumps(blueprint, indent=2, ensure_ascii=False), encoding="utf-8")
    ACTIVE_BLUEPRINT_FILE.write_text(json.dumps(blueprint, indent=2, ensure_ascii=False), encoding="utf-8")

    phil_name = str(blueprint.get("design_philosophy_name") or "Premium Editorial Principles")
    hier = str(blueprint.get("visual_hierarchy_principles") or "")
    print("\n✅ [SUCCESS] Master Design Principles Locked!")
    print(f"   🎨 Philosophy : {phil_name}")
    print(f"   📐 Hierarchy  : {hier[:120]}...")
    print(f"   💾 Saved To   : {ACTIVE_BLUEPRINT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
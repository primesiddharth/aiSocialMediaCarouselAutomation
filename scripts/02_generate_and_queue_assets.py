"""
Stage 2: Google Sheets-Driven Poster Generator (Creative Director + Exclusive Nano Banana 2.1)
- Reads pending rows from Google Sheets (19-column schema; all video fields removed)
- Combines Stage 1's abstract Design Principles (how to balance hierarchy, typography, lighting)
  with an Independent Creative Director LLM that freely invents the metaphor, objects, background,
  color palette, and composition best suited to each movie.
- Exclusively uses AIRouter (google/gemini-nano-banana-2.1) with a 420s timeout window.
- Uploads 1K Poster to ImgBB & syncs the 19-column row to Google Sheets via n8n Webhook.
"""
import argparse
import base64
import csv
import io
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\zero-touch-social-automation")
ENV_FILE = ROOT / ".env"
ACTIVE_BLUEPRINT_FILE = ROOT / "media_storage" / "ig_reference" / "active_style_blueprint.json"
OUT_DIR = ROOT / "media_storage" / "sheet_campaigns"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "HTTP-Referer": "https://zero-touch-n8n.onrender.com",
    "X-Title": "ZeroTouch Creative Director Engine",
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


def fetch_pending_sheet_rows(sheet_id: str, tab_name: str, max_rows: int) -> list[dict[str, str]]:
    export_url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={urllib.parse.quote(tab_name)}"
    )
    req = urllib.request.Request(export_url, headers=BROWSER_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            csv_text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            print(f"\n❌ [HTTP {e.code}] Cannot read Google Sheet! Ensure sharing is set to 'Anyone with the link'.")
            sys.exit(1)
        raise

    reader = csv.DictReader(io.StringIO(csv_text))
    pending: list[dict[str, str]] = []
    for row in reader:
        clean_row = {str(k or "").strip(): str(v or "").strip() for k, v in row.items() if k is not None}
        row_id = str(clean_row.get("#") or "").strip()
        dialogue = str(clean_row.get("Iconic Dialogue") or "").strip()
        angle = str(clean_row.get("Poster Advertising Angle") or "").strip()
        status = str(clean_row.get("Status") or "").strip().lower()
        li_draft = str(clean_row.get("LinkedIn_Post") or "").strip()
        img_url = str(clean_row.get("Image_URL") or "").strip()

        if row_id and dialogue and angle and (status in ("", "pending") or (status == "draft" and not img_url)) and (not li_draft or not img_url):
            pending.append(clean_row)
            if len(pending) >= max_rows:
                break
    return pending


def load_style_blueprint() -> dict[str, str]:
    if ACTIVE_BLUEPRINT_FILE.exists():
        try:
            raw = json.loads(ACTIVE_BLUEPRINT_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return {str(k): str(v or "") for k, v in raw.items()}
        except Exception:
            pass
    return {
        "reference_profile": "@creyotech_agency",
        "design_philosophy_name": "International Luxury Editorial",
        "visual_hierarchy_principles": "Commanding single focal metaphor with generous breathing room for headline legibility",
        "typography_craft_rules": "High-contrast display headline paired with a refined secondary callout pill",
        "color_harmony_principles": "Intentional emotional palette with sharp contrast between background and typography",
        "lighting_and_depth_principles": "Dramatic studio rim-lighting, realistic material reflections, and atmospheric depth",
    }


def discover_free_openrouter_models(api_key: str) -> list[str]:
    priority = ["gemma-4-31b", "nemotron-3-ultra", "nemotron-3.5-super", "gemma-4-26b", "xing4", "dots3", "lfm2.5"]
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


def call_openrouter_json(
    api_key: str, models: list[str], prompt: str, temperature: float = 0.8
) -> tuple[dict[str, Any] | None, str]:
    for model in models:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=json.dumps(
                {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": temperature}
            ).encode("utf-8"),
            headers={**BROWSER_HEADERS, "Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
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
                txt = str(first_msg.get("content") or "")
                txt = re.sub(r"<think>.*?</think>", "", txt, flags=re.DOTALL).strip()
                txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt, flags=re.IGNORECASE)
                s, e = txt.find("{"), txt.rfind("}")
                if s != -1 and e != -1:
                    cand = json.loads(txt[s : e + 1])
                    if isinstance(cand, dict):
                        return cand, model
        except Exception:
            time.sleep(1.2)
    return None, "fallback"


def invent_campaign_via_creative_director(
    api_key: str,
    row: dict[str, str],
    blueprint: dict[str, str],
    previous_concepts: list[str],
) -> dict[str, str]:
    """
    Pillar 2 (Creative Director):
    Uses Stage 1's abstract design principles ONLY for aesthetic quality (how to balance hierarchy,
    lighting, and typography), while independently inventing the metaphor, objects, background,
    colors, and composition for this specific movie.
    """
    row_id = str(row.get("#") or "1").strip()
    actor = str(row.get("Actor") or "").strip()
    movie = str(row.get("Movie (Year)") or "").strip()
    dialogue = str(row.get("Iconic Dialogue") or "").strip().strip('"').strip("'")
    angle = str(row.get("Poster Advertising Angle") or "").strip().strip('"').strip("'")
    li_m = str(row.get("LinkedIn_Mention") or "").strip()
    fb_m = str(row.get("Facebook_Mention") or "").strip()
    ig_m = str(row.get("Instagram_Mention") or "").strip()

    phil_name = str(blueprint.get("design_philosophy_name") or blueprint.get("design_system_name") or "Luxury Editorial")
    hierarchy_rule = str(blueprint.get("visual_hierarchy_principles") or blueprint.get("layout_architecture") or "Strong central focal hierarchy with generous negative space")
    typo_rule = str(blueprint.get("typography_craft_rules") or blueprint.get("typography_hierarchy") or "Ultra-crisp headline contrast")
    color_rule = str(blueprint.get("color_harmony_principles") or "Bold emotional color harmony")
    lighting_rule = str(blueprint.get("lighting_and_depth_principles") or "Dramatic studio lighting and depth")

    avoid_list = " | ".join(previous_concepts) if previous_concepts else "None yet"

    director_prompt = (
        "You are an International Executive Creative Director for Creyotech (a premier Website Design & Digital Engineering Agency).\n"
        f"You are creating an original, breathtaking 1024x1024 (1K resolution, 1:1 square) advertisement inspired by:\n"
        f"- Movie: '{movie}' ({actor})\n"
        f"- Iconic Dialogue: \"{dialogue}\"\n"
        f"- Creyotech Advertising Hook: \"{angle}\"\n\n"
        f"DESIGN QUALITY PRINCIPLES (Learned from {phil_name} — use these to guide HOW you balance the design, NOT as rigid objects/colors):\n"
        f"- Hierarchy Philosophy: {hierarchy_rule}\n"
        f"- Typography Craft: {typo_rule}\n"
        f"- Color Harmony Logic: {color_rule}\n"
        f"- Lighting & Depth: {lighting_rule}\n\n"
        "YOUR CREATIVE FREEDOM (Invent Independently for this Movie):\n"
        "1. Invent an unforgettable, movie-specific symbolic metaphor and environment (e.g., for 'Don (2006)': an obsidian chess-king inside an emerald laser security vault; "
        "for 'Om Shanti Om': a majestic golden chandelier refracting into luminous digital glass prisms on a grand red-velvet stage; "
        "for 'Jab We Met': a kinetic neon-lit express train hurtling through a surreal starlit horizon; "
        "for 'Mr. India': an iconic ruby-red chronograph watch bending invisible light waves; "
        "for 'Shahenshah': a monumental brushed-steel royal emblem and electric lightning over a nocturnal metropolis).\n"
        "2. Choose the exact color palette, background atmosphere, and composition that create the strongest impact for THIS movie.\n"
        f"3. Do NOT repeat any of these previous concepts: [{avoid_list}].\n"
        "4. STRICT NEGATIVE GUARDRAILS: ZERO human faces, NO portraits, NO film reels, NO clapperboards, NO movie projectors.\n"
        "5. MANDATORY VERBATIM TEXT ON THE POSTER: Instruct the image model to render these exact 3 text strings with flawless spelling:\n"
        f"   - Hero Headline: \"{dialogue}\"\n"
        f"   - Sub-Headline Callout: \"{angle}\"\n"
        "   - Brand Footer Pill: \"WEBSITE DESIGN | CREYOTECH\"\n\n"
        "Return ONLY valid raw JSON (no markdown blocks) with these exact keys:\n"
        "{\n"
        '  "concept_summary": "1-sentence summary of your bespoke metaphor, palette, and composition",\n'
        '  "image_gen_prompt": "Natural, vivid, un-cluttered 90-to-110-word prompt for Nano Banana 2.1 describing the bespoke advertisement",\n'
        '  "image_description": "Concise alt-text describing the poster",\n'
        '  "linkedin_post": "Professional LinkedIn post including the dialogue and angle verbatim",\n'
        '  "facebook_post": "Engaging Facebook post including the dialogue and angle verbatim",\n'
        '  "instagram_post": "High-impact Instagram caption with emojis and hashtags"\n'
        "}"
    )

    models = discover_free_openrouter_models(api_key)
    print(f"     🧠 [Creative Director] Inventing original campaign concept for '{movie}' via {models[0]}...")
    res_json, model_used = call_openrouter_json(api_key, models, director_prompt, temperature=0.8)

    if res_json and res_json.get("image_gen_prompt"):
        concept_str = str(res_json.get("concept_summary") or "")
        print(f"     ✨ [Concept Locked via {model_used}]: {concept_str[:100]}...")
        img_prompt = str(res_json.get("image_gen_prompt") or "").strip()
        if dialogue.lower() not in img_prompt.lower():
            img_prompt += f' Render primary headline text: "{dialogue}".'
        if angle.lower() not in img_prompt.lower():
            img_prompt += f' Render secondary callout text: "{angle}".'
        if "creyotech" not in img_prompt.lower():
            img_prompt += ' Render footer badge: "WEBSITE DESIGN | CREYOTECH".'
        img_prompt += " Strictly faceless (no human faces), no film reels, no clapperboards."
    else:
        concept_str = f"Bespoke luxury technology campaign inspired by {movie}"
        img_prompt = (
            f"Create a breathtaking 1024x1024 (1K resolution, 1:1 square) international luxury technology advertisement "
            f"inspired by the iconic mood of '{movie}' ({actor}). Use a powerful symbolic 3D metaphor, dramatic studio lighting, "
            f"sophisticated editorial composition, and intentional negative space (no human faces, no film reels, no clapperboards). "
            f"Render exact typography on the poster: 1. Primary Hero Headline: \"{dialogue}\" "
            f"2. Secondary Callout Pill: \"{angle}\" 3. Footer Badge: \"WEBSITE DESIGN | CREYOTECH\"."
        )
        res_json = {}

    previous_concepts.append(f"{movie}: {concept_str}")

    def enforce_verbatim(text: str, mention: str, default_body: str) -> str:
        t = str(text or default_body).strip()
        if dialogue.lower() not in t.lower():
            t = f"\"{dialogue}\"\n\n{t}"
        if angle.lower() not in t.lower():
            t = f"{t}\n\n🎯 {angle}"
        if mention and mention.lower() not in t.lower():
            t = f"{t}\n\ncc: {mention}"
        return t

    li_default = f"\"{dialogue}\"\n\nInspired by {movie}, your digital presence deserves world-class engineering.\n\n🎯 {angle}\n\n#WebsiteDesign #Creyotech #DigitalStrategy"
    fb_default = f"\"{dialogue}\" ✨\n\n🎯 {angle}\n\nTransform your brand online with Creyotech! #Creyotech #WebsiteDesign"
    ig_default = f"\"{dialogue}\" 🔥\n\n🎯 {angle}\n\n🚀 DM Creyotech to elevate your web presence!\n\n#Creyotech #WebsiteDesign #UIUX"

    return {
        "concept_summary": concept_str,
        "image_gen_prompt": img_prompt,
        "image_description": str(res_json.get("image_description") or f"{movie} ({actor}) Ad Poster: \"{dialogue}\" — {angle}"),
        "linkedin_post": enforce_verbatim(str(res_json.get("linkedin_post") or ""), li_m, li_default),
        "facebook_post": enforce_verbatim(str(res_json.get("facebook_post") or ""), fb_m, fb_default),
        "instagram_post": enforce_verbatim(str(res_json.get("instagram_post") or ""), ig_m, ig_default),
    }


def extract_image_bytes_from_airouter(data: dict[str, Any]) -> bytes:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        preview = json.dumps(data)[:250]
        raise RuntimeError(f"No 'choices' in AIRouter response: {preview}")

    first_choice = choices[0]
    message = first_choice.get("message") if isinstance(first_choice, dict) else {}
    if not isinstance(message, dict):
        message = {}

    def decode_candidate(val: str) -> bytes | None:
        trimmed = val.strip()
        if trimmed.startswith("data:image"):
            return base64.b64decode(trimmed.split(",", 1)[1])
        if trimmed.startswith("http://") or trimmed.startswith("https://"):
            req = urllib.request.Request(trimmed, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        if len(trimmed) > 256 and re.match(r"^[A-Za-z0-9+/=\r\n]+$", trimmed):
            return base64.b64decode(trimmed)
        return None

    for img_item in message.get("images") or []:
        if isinstance(img_item, str):
            res = decode_candidate(img_item)
            if res is not None:
                return res
        elif isinstance(img_item, dict):
            nested = img_item.get("image_url")
            nested_url = nested.get("url") if isinstance(nested, dict) else nested
            for cand in [nested_url, img_item.get("url"), img_item.get("b64_json"), img_item.get("data")]:
                if isinstance(cand, str) and cand:
                    res = decode_candidate(cand)
                    if res is not None:
                        return res

    content = message.get("content")
    if isinstance(content, str) and content:
        m = re.search(r"(data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=]+)", content)
        if m:
            res = decode_candidate(m.group(1))
            if res is not None:
                return res
        u = re.search(r"(https?://[^\s\)\"'>]+)", content)
        if u:
            res = decode_candidate(u.group(1))
            if res is not None:
                return res

    raise RuntimeError("Could not extract image bytes from AIRouter response.")


class AIRouterBillingError(RuntimeError):
    """Raised when AIRouter rejects generation due to insufficient credits (HTTP 402)."""


def _read_http_error_body(err: urllib.error.HTTPError) -> str:
    try:
        raw = err.read().decode("utf-8", errors="replace")
        return raw[:1200] if raw else ""
    except Exception:
        return ""


def generate_airouter_1k_poster(
    api_key: str,
    base_url: str,
    model: str,
    prompt: str,
    timeout_secs: int = 420,
) -> bytes:
    """
    Exclusively uses AIRouter (google/gemini-nano-banana-2.1) with an expanded 420s timeout window.
    No fallback models are used.
    """
    if not api_key.strip():
        raise RuntimeError("AIROUTER_API_KEY is missing from .env.")

    url = f"{base_url.rstrip('/')}/chat/completions"
    retry_delays = [6, 12, 20]

    for attempt in range(1, 4):
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["image", "text"],
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                **BROWSER_HEADERS,
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        print(f"     -> [Nano Banana 2.1 Attempt {attempt}/3] Requesting {model} (timeout={timeout_secs}s)...")
        try:
            with urllib.request.urlopen(req, timeout=timeout_secs) as resp:
                raw_resp = json.loads(resp.read().decode("utf-8"))
                return extract_image_bytes_from_airouter(raw_resp)
        except urllib.error.HTTPError as err:
            body = _read_http_error_body(err)
            if err.code == 402:
                raise AIRouterBillingError(
                    f"AIRouter returned HTTP 402 (Insufficient Credits). Response: {body}"
                ) from err
            if err.code in (400, 401, 403, 404) or attempt == 3:
                raise RuntimeError(f"AIRouter HTTP {err.code}: {body}") from err
            wait_s = retry_delays[attempt - 1]
            print(f"     ⚠️ Transient HTTP {err.code}; retrying in {wait_s}s...")
            time.sleep(wait_s)
        except Exception as err:
            if attempt == 3:
                raise RuntimeError(f"AIRouter failed after 3 attempts: {err}") from err
            wait_s = retry_delays[attempt - 1]
            print(f"     ⚠️ Network/timeout warning ({err}); retrying in {wait_s}s...")
            time.sleep(wait_s)

    raise RuntimeError("AIRouter poster generation failed.")


def upload_bytes_to_imgbb(imgbb_key: str, img_bytes: bytes, name_prefix: str) -> str:
    boundary = f"----ZeroTouchBoundary{uuid.uuid4().hex}"
    filename = f"{name_prefix}_{int(time.time())}.png"
    body = b"".join([
        f'--{boundary}\r\nContent-Disposition: form-data; name="key"\r\n\r\n{imgbb_key}\r\n'.encode("utf-8"),
        f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="{filename}"\r\nContent-Type: image/png\r\n\r\n'.encode("utf-8"),
        img_bytes,
        f"\r\n--{boundary}--\r\n".encode("utf-8"),
    ])
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(
                "https://api.imgbb.com/1/upload",
                data=body,
                headers={
                    "Content-Type": f"multipart/form-data; boundary={boundary}",
                    "Content-Length": str(len(body)),
                    "User-Agent": "Mozilla/5.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                data_obj = json.loads(resp.read().decode("utf-8")).get("data") or {}
                url_str = str(data_obj.get("url") or "").strip()
                if url_str:
                    return url_str
        except Exception:
            if attempt == 3:
                raise
            time.sleep(3)
    raise RuntimeError("ImgBB upload failed")


def sync_row_to_n8n_webhook(webhook_base: str, row_payload: dict[str, str]) -> bool:
    req = urllib.request.Request(
        f"{webhook_base.rstrip('/')}/webhook/sheet-row-update",
        data=json.dumps(row_payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status in (200, 201)
    except Exception as e:
        print(f"     ⚠️ Webhook sync notice ({e}) — ensure Workflow 1 is Active on Render.")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 2: Creative Director + Exclusive Nano Banana 2.1 Poster Pipeline")
    parser.add_argument("--limit", type=int, default=1, help="Number of pending Google Sheet rows to process")
    parser.add_argument("--status", default="Draft", choices=["Draft", "Approved"], help="Target status after generation")
    parser.add_argument("--regen", action="store_true", help="Force regenerate poster even if cached locally")
    args = parser.parse_args()

    env = load_env(ENV_FILE)
    sheet_id = str(env.get("GOOGLE_SHEET_DOCUMENT_ID") or "").strip()
    tab_name = str(env.get("GOOGLE_SHEET_TAB_NAME") or "Content_Pipeline")
    openrouter_key = str(env.get("OPENROUTER_API_KEY") or "").strip()
    airouter_key = str(env.get("AIROUTER_API_KEY") or "").strip()
    airouter_base = str(env.get("AIROUTER_BASE_URL") or "https://api.airouter.in/v1")
    airouter_model = str(env.get("AIROUTER_IMAGE_MODEL") or "google/gemini-nano-banana-2.1")
    timeout_secs = int(str(env.get("AIROUTER_TIMEOUT_SECONDS") or "420"))
    imgbb_key = str(env.get("IMGBB_API_KEY") or "").strip()
    webhook_base = str(env.get("WEBHOOK_URL") or "https://zero-touch-n8n.onrender.com/")

    blueprint = load_style_blueprint()
    phil_title = blueprint.get("design_philosophy_name") or blueprint.get("design_system_name") or "Editorial Principles"
    print(f"🎨 [DESIGN PRINCIPLES LOADED] {phil_title} (learned from {blueprint.get('reference_profile')})")

    print(f"📊 [GOOGLE SHEETS] Fetching up to {args.limit} pending row(s) from '{tab_name}'...")
    pending_rows = fetch_pending_sheet_rows(sheet_id, tab_name, args.limit)
    if not pending_rows:
        print("ℹ️ No pending rows found in Google Sheets.")
        sys.exit(0)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    updated_rows: list[dict[str, str]] = []
    previous_concepts: list[str] = []

    for row in pending_rows:
        row_id = str(row.get("#") or "").strip()
        actor = str(row.get("Actor") or "").strip()
        movie = str(row.get("Movie (Year)") or "").strip()
        dialogue = str(row.get("Iconic Dialogue") or "").strip()
        angle = str(row.get("Poster Advertising Angle") or "").strip()

        inc_img_raw = str(row.get("Include Image?") or "Yes").strip().lower()
        include_image = "No" if inc_img_raw in ("no", "false", "0") else "Yes"

        print(f"\n🚀 [ROW #{row_id}] {movie} ({actor}) | Include Image: {include_image}")
        creative_pack = invent_campaign_via_creative_director(openrouter_key, row, blueprint, previous_concepts)

        image_url = ""
        row_errors: list[str] = []
        if include_image == "Yes":
            poster_path = OUT_DIR / f"row_{row_id}_1k_poster.png"
            prompt_path = OUT_DIR / f"row_{row_id}_poster_prompt.txt"
            prompt_path.write_text(creative_pack["image_gen_prompt"], encoding="utf-8")

            try:
                if poster_path.exists() and poster_path.stat().st_size > 10000 and not args.regen:
                    img_bytes = poster_path.read_bytes()
                    print(f"     ♻️ [POSTER CACHE] Using cached 1K poster -> {poster_path.name}")
                else:
                    img_bytes = generate_airouter_1k_poster(
                        airouter_key,
                        airouter_base,
                        airouter_model,
                        creative_pack["image_gen_prompt"],
                        timeout_secs=timeout_secs,
                    )
                    poster_path.write_bytes(img_bytes)
                    print(f"     ✅ [OK] Saved 1K Poster ({len(img_bytes):,} bytes) -> {poster_path.name}")

                print("     -> Uploading 1K Poster to ImgBB...")
                image_url = upload_bytes_to_imgbb(imgbb_key, img_bytes, f"row_{row_id}_creyotech")
                print(f"     ✅ [OK] Image_URL: {image_url}")
            except Exception as err:
                row_errors.append(str(err))
                print(f"     ❌ [POSTER ERROR] {err}")

        final_row: dict[str, str] = {
            "#": row_id,
            "Actor": actor,
            "Movie (Year)": movie,
            "Iconic Dialogue": dialogue,
            "Poster Advertising Angle": angle,
            "Include Image?": include_image,
            "LinkedIn_Mention": str(row.get("LinkedIn_Mention") or ""),
            "Facebook_Mention": str(row.get("Facebook_Mention") or ""),
            "Instagram_Mention": str(row.get("Instagram_Mention") or ""),
            "Status": "Draft" if row_errors else str(args.status),
            "LinkedIn_Post": creative_pack["linkedin_post"],
            "Facebook_Post": creative_pack["facebook_post"],
            "Instagram_Post": creative_pack["instagram_post"],
            "Image_Gen_Prompt": creative_pack["image_gen_prompt"] if include_image == "Yes" else "",
            "Image_Description": creative_pack["image_description"] if include_image == "Yes" else "",
            "Image_URL": image_url,
            "Buffer_Update_IDs": str(row.get("Buffer_Update_IDs") or ""),
            "Error_Message": " | ".join(row_errors),
            "Actual Post Date": str(row.get("Actual Post Date") or ""),
        }
        updated_rows.append(final_row)

        if sync_row_to_n8n_webhook(webhook_base, final_row):
            print(f"     ✅ [SHEET SYNCED] Row #{row_id} updated in Google Sheets via n8n!")

    out_csv = OUT_DIR / "updated_sheet_rows.csv"
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(updated_rows[0].keys()))
        writer.writeheader()
        writer.writerows(updated_rows)
    print(f"\n📦 [COMPLETE] Saved {len(updated_rows)} processed campaign row(s) -> {out_csv.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
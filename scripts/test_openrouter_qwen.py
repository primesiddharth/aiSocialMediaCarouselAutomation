"""
Standalone Pre-Flight Test for OpenRouter Dynamic Free LLM Routing.
Dynamically fetches active free models from https://openrouter.ai/api/v1/models,
filters by "pricing": {"prompt": "0", "completion": "0"}, and executes the
meta-prompt payload against the first operational free model with automated 404/429 continue loops.
"""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Ensure UTF-8 console output for Windows CLI
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\zero-touch-social-automation")
ENV_FILE = ROOT / ".env"
SYS_PROMPT_FILE = ROOT / "prompts" / "strategist_system_prompt.txt"

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

def extract_json(raw_text: str) -> dict:
    cleaned = raw_text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)

def fetch_dynamic_free_models(api_key: str, base_url: str) -> list[str]:
    """Pings /models, parses JSON, and filters models with 0-cost pricing."""
    models_url = f"{base_url.rstrip('/')}/models"
    req = urllib.request.Request(
        models_url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": "https://zero-touch-n8n.onrender.com",
            "X-Title": "Zero-Touch Social Automation",
        },
        method="GET"
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            free_models: list[str] = []
            for item in data.get("data", []):
                pricing = item.get("pricing", {})
                p = str(pricing.get("prompt", ""))
                c = str(pricing.get("completion", ""))
                # Strictly filter for models returning prompt=0 and completion=0
                if p in ("0", "0.0") and c in ("0", "0.0"):
                    model_id = item.get("id")
                    if model_id and not any(skip in model_id for skip in ["clip", "embed"]):
                        free_models.append(model_id)
            print(f"  -> Discovered {len(free_models)} dynamic 0-cost free models on OpenRouter.")
            return free_models
    except Exception as exc:
        print(f"  [WARN] Failed to fetch dynamic models from {models_url}: {exc}")
        return []

def call_openrouter(api_key: str, base_url: str, model: str, system_prompt: str, user_prompt: str) -> dict:
    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://zero-touch-n8n.onrender.com",
            "X-Title": "Zero-Touch Social Automation",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        content = data["choices"][0]["message"]["content"]
        return extract_json(content)

def main() -> None:
    print("🧠 Testing OpenRouter AI Strategist (Dynamic Free LLM Routing)...\n")
    env = load_env(ENV_FILE)
    api_key = env.get("OPENROUTER_API_KEY", "")
    raw_base_url = env.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    # Clean any accidental markdown link wrapping
    base_url = re.sub(r"[\[\]\(\)]", "", raw_base_url).strip()
    if not base_url.startswith("http"):
        base_url = "https://openrouter.ai/api/v1"

    configured_model = env.get("OPENROUTER_MODEL", "")

    if not api_key or "xxxx" in api_key:
        print("❌ [FAIL] OPENROUTER_API_KEY in .env is still a placeholder!")
        sys.exit(1)

    system_prompt = SYS_PROMPT_FILE.read_text(encoding="utf-8")
    user_prompt = "Topic: Backend live! | Image Needed: No | Mentions: @JaneDoe"

    # Step 2: Dynamically query OpenRouter models API for 0-cost free models
    dynamic_models = fetch_dynamic_free_models(api_key, base_url)
    
    # Priority order: configured model if valid, followed by dynamic free models
    models_to_try: list[str] = []
    if configured_model and configured_model in dynamic_models:
        models_to_try.append(configured_model)
    for m in dynamic_models:
        if m not in models_to_try:
            models_to_try.append(m)
            
    # Fallback catalog if dynamic discovery was empty
    static_fallbacks = [
        "nvidia/nemotron-3.5-super-vl:free",
        "nvidia/nemotron-3.5-lightning:free",
        "google/gemma-4-26b-a4b-it:free",
        "meta-llama/llama-3.1-8b-instruct:free",
    ]
    for sf in static_fallbacks:
        if sf not in models_to_try:
            models_to_try.append(sf)

    parsed_json = None
    active_model = None

    for model in models_to_try:
        print(f"  -> Attempting model: {model} ...")
        try:
            parsed_json = call_openrouter(api_key, base_url, model, system_prompt, user_prompt)
            active_model = model
            break
        except urllib.error.HTTPError as he:
            err_body = he.read().decode("utf-8", errors="ignore")
            # Step 2: Implement automated continue loop for 404s, 429s, or other rotating errors
            if he.code in (404, 429, 503):
                print(f"     [WARN] {model} returned HTTP {he.code} (rotating availability/rate limit). Continuing...")
                continue
            print(f"     [WARN] {model} returned HTTP {he.code}: {err_body[:160]}. Continuing...")
            continue
        except Exception as exc:
            print(f"     [WARN] {model} failed: {exc}. Continuing...")
            continue

    if not parsed_json:
        print("❌ [FAIL] All OpenRouter free models failed. Verify your API key & Privacy settings at https://openrouter.ai/settings/privacy")
        sys.exit(1)

    print(f"\n✅ [PASS] Received structured JSON from {active_model}:")
    print(json.dumps(parsed_json, indent=2, ensure_ascii=False))

    # Validate required keys & PDF business rules
    required_keys = ["linkedin_post", "facebook_post", "instagram_post", "image_gen_prompt", "image_description"]
    for k in required_keys:
        if k not in parsed_json:
            print(f"❌ [FAIL] Missing required key in JSON output: {k}")
            sys.exit(1)

    if "@JaneDoe" not in parsed_json["linkedin_post"]:
        print("⚠️  [WARN] '@JaneDoe' was not found in linkedin_post.")
    else:
        print("✅ [PASS] '@JaneDoe' naturally woven into platform copy!")

    if parsed_json["image_gen_prompt"] is None:
        print("✅ [PASS] 'image_gen_prompt' is strictly null when Image Needed = No!")
    else:
        print(f"⚠️  [WARN] Expected image_gen_prompt to be null, got: {parsed_json['image_gen_prompt']}")

if __name__ == "__main__":
    main()
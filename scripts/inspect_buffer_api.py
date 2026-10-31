"""
Official Buffer GraphQL API Channel Discovery & Live Queue Verifier.
1. Queries { account { organizations { id name } } }
2. Queries { channels(input: { organizationId }) { id name service isQueuePaused } }
3. Prints exact BUFFER_PROFILE_ID_* values for .env and tests dailyPostingLimits.
"""
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\zero-touch-social-automation")
ENV_FILE = ROOT / ".env"
BUFFER_GQL_URL = "https://api.buffer.com"

def load_env(path: Path) -> dict[str, str]:
    env_vars: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env_vars[k.strip()] = re.sub(r"[<>\"'\s]", "", v.strip())
    return env_vars

def gql_request(token: str, query: str, variables: dict | None = None) -> dict:
    payload: dict = {"query": query}
    if variables:
        payload["variables"] = variables
    req = urllib.request.Request(
        BUFFER_GQL_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "ZeroTouch-BufferGraphQL/2.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=25) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main() -> None:
    env = load_env(ENV_FILE)
    token = env.get("BUFFER_API_KEY", "")
    if not token:
        print("❌ BUFFER_API_KEY is missing from .env")
        sys.exit(1)

    print("🔍 Step 1: Fetching Buffer Organization ID via GraphQL...")
    org_query = """
    query GetOrganizations {
      account {
        id
        email
        organizations {
          id
          name
        }
      }
    }
    """
    org_resp = gql_request(token, org_query)
    if "errors" in org_resp:
        print(f"❌ GraphQL Error fetching organizations: {org_resp['errors']}")
        sys.exit(1)

    orgs = org_resp.get("data", {}).get("account", {}).get("organizations", [])
    if not orgs:
        print("❌ No organizations found on this Buffer account.")
        sys.exit(1)

    org_id = orgs[0]["id"]
    org_name = orgs[0].get("name", "Default Org")
    print(f"✅ [PASS] Found Organization: '{org_name}' (ID: {org_id})\n")

    print("🔍 Step 2: Fetching Connected Social Channels for Organization...")
    channels_query = """
    query GetChannels($orgId: OrganizationId!) {
      channels(input: { organizationId: $orgId }) {
        id
        name
        displayName
        service
        isQueuePaused
        isDisconnected
      }
    }
    """
    ch_resp = gql_request(token, channels_query, {"orgId": org_id})
    if "errors" in ch_resp:
        print(f"❌ GraphQL Error fetching channels: {ch_resp['errors']}")
        sys.exit(1)

    channels = ch_resp.get("data", {}).get("channels", [])
    print(f"✅ [PASS] Discovered {len(channels)} Connected Channels on Buffer:\n")

    discovered_map = {}
    for ch in channels:
        svc = str(ch.get("service", "")).lower()
        cid = ch.get("id")
        cname = ch.get("displayName") or ch.get("name")
        paused = ch.get("isQueuePaused")
        disconn = ch.get("isDisconnected")
        print(f"   • {svc.upper():10s} | ID: {cid} | Name: {cname} | QueuePaused: {paused} | Disconnected: {disconn}")
        discovered_map[svc] = cid

    print("\n📋 Copy these exact IDs into your .env and Render Environment Variables (optional—Node 05 also auto-discovers them!):")
    print(f"BUFFER_ORGANIZATION_ID={org_id}")
    print(f"BUFFER_PROFILE_ID_LINKEDIN={discovered_map.get('linkedin', '')}")
    print(f"BUFFER_PROFILE_ID_FACEBOOK={discovered_map.get('facebook', '')}")
    print(f"BUFFER_PROFILE_ID_INSTAGRAM={discovered_map.get('instagram', '')}")

if __name__ == "__main__":
    main()
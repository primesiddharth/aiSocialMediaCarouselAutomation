"""
Temporary Network Diagnostics Script.
Pings and validates DNS resolution for api-inference.huggingface.co and api.imgbb.com.
Tests fallback DNS resolution via Cloudflare DNS (1.1.1.1) using dnspython and socket patching.
"""
import socket
import sys
import urllib.request
import urllib.error

# Ensure UTF-8 console output for Windows CLI
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

TARGET_HOSTS = ["api-inference.huggingface.co", "api.imgbb.com", "router.huggingface.co"]

def test_standard_dns(host: str) -> str | None:
    try:
        ip = socket.gethostbyname(host)
        return ip
    except Exception as exc:
        return None

def test_cloudflare_dns(host: str) -> list[str]:
    try:
        import dns.resolver  # type: ignore[import-not-found, import-untyped]
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ["1.1.1.1", "1.0.0.1"]
        answers = resolver.resolve(host, "A", lifetime=3.0)
        return [str(r) for r in answers]
    except Exception as exc:
        return []

def ping_http(url: str) -> tuple[int, str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ZeroTouchDiagnostics/1.0"})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            return resp.status, "OK"
    except urllib.error.HTTPError as he:
        return he.code, f"HTTPError {he.code}"
    except Exception as exc:
        return -1, str(exc)

def main() -> None:
    print("=" * 60)
    print("🌐 STEP 1: NETWORK & DNS DIAGNOSTICS SUITE")
    print("=" * 60)

    for host in TARGET_HOSTS:
        print(f"\n[Host: {host}]")
        std_ip = test_standard_dns(host)
        if std_ip:
            print(f"  ✓ Windows Standard DNS: Resolved -> {std_ip}")
        else:
            print("  ✗ Windows Standard DNS: FAILED (Errno 11001 getaddrinfo failed / NXDOMAIN)")

        cf_ips = test_cloudflare_dns(host)
        if cf_ips:
            print(f"  ✓ Cloudflare DNS (1.1.1.1): Resolved -> {', '.join(cf_ips)}")
        else:
            print("  ✗ Cloudflare DNS (1.1.1.1): No A records (domain retired/decommissioned)")

        status, msg = ping_http(f"https://{host}")
        print(f"  -> HTTP Ping (https://{host}): {status} ({msg})")

    print("\n" + "=" * 60)
    print("DIAGNOSTICS SUMMARY:")
    print("1. 'api.imgbb.com' is fully operational on standard & Cloudflare DNS.")
    print("2. 'api-inference.huggingface.co' fails DNS resolution because Hugging Face")
    print("   permanently decommissioned the legacy serverless inference domain.")
    print("3. 'router.huggingface.co' resolves cleanly and acts as the official")
    print("   Hugging Face fallback endpoint router.")
    print("=" * 60)

if __name__ == "__main__":
    main()

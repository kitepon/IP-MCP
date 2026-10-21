"""Check the deployed trust stores without reading credentials or calling JPO APIs."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.metadata
import json
import ssl
import subprocess

import certifi
import httpx

from ip_mcp.jpo.client import JpoClient, JpoConfig

G3 = "86a1ecba089c4a8d3bbe2734c612ba341d813e043cf9e8a862cd5c57a36bbe6b"
AAA = "d7a7a0fb5d7e2731d771e9484ebcdef71d5f0c3e0a2948782bc83ee0ea699ef4"
G1 = "40f6af0346a99aa1cd1d555a4e9cce62c7f9634603ee406615833dc8c8d00367"


def inspect_store(context: ssl.SSLContext) -> dict[str, object]:
    roots = {hashlib.sha256(der).hexdigest() for der in context.get_ca_certs(binary_form=True)}
    return {"count": len(roots), "g3": G3 in roots, "aaa": AAA in roots, "g1": G1 in roots}


def bundle_context(path: str) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cafile=path)
    return context


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


async def check(tls: bool) -> dict[str, object]:
    ca_version = subprocess.check_output(
        ["dpkg-query", "-W", "-f=${Version}", "ca-certificates"], text=True
    ).strip()
    subprocess.run(["dpkg", "--compare-versions", ca_version, "ge", "20250419+deb13u1"], check=True)
    require(importlib.metadata.version("certifi") == "2026.10.19", "Unexpected certifi version")
    jpo = JpoClient(config=JpoConfig())
    async with httpx.AsyncClient(timeout=20.0) as external:
        try:
            stores = {
                "os": inspect_store(bundle_context("/etc/ssl/certs/ca-certificates.crt")),
                "certifi": inspect_store(bundle_context(certifi.where())),
                # Inspect the actual client contexts, including HTTPX environment handling.
                "jpo_httpx": inspect_store(jpo._http._transport._pool._ssl_context),
                "external_httpx": inspect_store(external._transport._pool._ssl_context),
            }
            for name, roots in stores.items():
                require(not roots["g3"], f"G3 remains in {name}")
                require(bool(roots["g1"]), f"G1 is missing from {name}")
            require(not stores["os"]["aaa"], "AAA remains in the Debian bundle")
            result: dict[str, object] = {
                "ca_certificates": ca_version,
                "certifi": importlib.metadata.version("certifi"),
                "certifi_path": certifi.where(),
                "stores": stores,
            }
            if tls:
                # Static landing pages only: no credentials, patent lookups, or API quota.
                responses = await asyncio.gather(
                    jpo._http.get("https://ip-data.jpo.go.jp/"),
                    external.get("https://patents.google.com/"),
                )
                result["tls"] = {str(r.url): r.status_code for r in responses}
            return result
        finally:
            await jpo._http.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tls", action="store_true", help="Also check ordinary outbound TLS")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(check(args.tls)), indent=2))

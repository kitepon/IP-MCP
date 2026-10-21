# Trust-store security update

The normal Dockerfile uses Debian trixie, requires the ca-certificates update
from DSA-6572-1, and checks the OS bundle, certifi bundle, and the actual HTTPX
client contexts at build time. certifi is pinned to 2026.10.19 in pyproject.toml
and uv.lock.

`security-update.Dockerfile` also supports a narrow update to an existing
production image. It changes ca-certificates and certifi while retaining the
application and its other Python packages. First record and verify the current
image ID, then give that exact local image a dedicated alias:

```sh
docker tag <recorded-image-ID> ip-mcp:sec021-base-d419dcd571ca
docker image inspect --format '{{.Id}}' ip-mcp:sec021-base-d419dcd571ca
# Stop if the output differs from the recorded ID.
docker build --target runtime -f docker/security-update.Dockerfile \
  --build-arg BASE_IMAGE=ip-mcp:sec021-base-d419dcd571ca -t ip-mcp:security-candidate .
docker build --target test -f docker/security-update.Dockerfile \
  --build-arg BASE_IMAGE=ip-mcp:sec021-base-d419dcd571ca -t ip-mcp:security-tests .
docker run --rm ip-mcp:security-candidate python /app/scripts/check_trust_store.py --tls
```

BuildKit treats a bare `sha256:ID` in FROM as a registry image name, so the
verified alias is required for locally built images without a repository digest.
Record the resulting candidate image ID as well; validate and deploy that exact
image. The test target installs test-only packages and must not be deployed.

Build contexts must exclude `.env`, database files, cache, and logs. The narrow
update only needs `docker/`, `scripts/check_trust_store.py`, and `tests/`.
Isolation tests must use synthetic OAuth credentials and data, without mounting
production directories or publishing a service port.

The optional TLS check requests only the JPO and Google Patents landing pages.
It does not authenticate, look up patents, or establish that all product tools
work with real API credentials. The checks establish trust-store contents and
ordinary TLS connectivity, not the absence of past compromise.

Before production replacement, retain the old image and take a consistent SQLite
backup. Reuse the same data/cache/log mounts on replacement and rollback. Do not
restore an older database during an ordinary image rollback; retain current data
and verify that existing OAuth registrations and tokens survive. Rolling back the
image also restores the old trust stores.

References: [Debian DSA-6572-1](https://lists.debian.org/debian-security-announce/2026/msg00487.html),
[certifi 2026.10.19](https://pypi.org/project/certifi/2026.10.19/),
[HTTPX SSL configuration](https://www.python-httpx.org/advanced/ssl/).

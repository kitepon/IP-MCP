# Apply the trust-store fix to the inspected production image.
# First tag the recorded image ID with a dedicated alias and verify the alias.
# BuildKit interprets a bare sha256:ID as a registry name, so use that local alias.
ARG BASE_IMAGE=ip-mcp:sec021-base-d419dcd571ca
FROM ${BASE_IMAGE} AS runtime

RUN apt-get update \
 && apt-get install -y --no-install-recommends --only-upgrade ca-certificates \
 && dpkg --compare-versions "$(dpkg-query -W -f='${Version}' ca-certificates)" ge 20250419+deb13u1 \
 && rm -rf /var/lib/apt/lists/*

COPY docker/certifi-requirements.txt /tmp/certifi-requirements.txt
RUN python -m pip install --no-cache-dir --no-deps --require-hashes -r /tmp/certifi-requirements.txt \
 && rm /tmp/certifi-requirements.txt
COPY scripts/check_trust_store.py /app/scripts/check_trust_store.py
RUN python /app/scripts/check_trust_store.py

FROM runtime AS test
COPY tests /tmp/ip-mcp-tests
RUN uv pip install --system --no-cache pytest==9.0.3 pytest-asyncio==1.3.0 pytest-httpx==0.36.2
RUN python -c "import pathlib,ip_mcp; p=pathlib.Path('/tmp/src'); p.mkdir(); (p/'ip_mcp').symlink_to(pathlib.Path(ip_mcp.__file__).parent)"
RUN cd /tmp && python -m pytest -q -o asyncio_mode=auto ip-mcp-tests

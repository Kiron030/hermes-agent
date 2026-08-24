# R5 egress broker. Sandbox infrastructure, not Hermes core.
#
# FROM the same pinned Hermes digest the Developer image uses. That is not
# convenience: the official upstream egress component lives at
# agent/proxy_sources/iron_proxy.py inside this image, so building on it lets
# the broker reuse upstream's config schema, CA generation and token
# substitution without adding a second supply chain or patching Hermes core.
FROM nousresearch/hermes-agent@sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09

USER root

ARG IRON_PROXY_VERSION
ARG IRON_PROXY_SHA256
ARG IRON_PROXY_ASSET

# The binary is verified against the SHA-256 published in the release's
# checksums.txt and recorded in broker_contract.json. A mismatch fails the
# build; there is no floating tag and no "latest" anywhere in this path.
RUN set -eu; \
    url="https://github.com/ironsh/iron-proxy/releases/download/v${IRON_PROXY_VERSION}/${IRON_PROXY_ASSET}"; \
    curl -fsSL "$url" -o /tmp/iron-proxy.tar.gz; \
    printf '%s  %s\n' "${IRON_PROXY_SHA256}" /tmp/iron-proxy.tar.gz | sha256sum -c -; \
    mkdir -p /opt/r5-egress/bin; \
    tar -xzf /tmp/iron-proxy.tar.gz -C /opt/r5-egress/bin --strip-components=0 iron-proxy; \
    rm -f /tmp/iron-proxy.tar.gz; \
    chmod 0755 /opt/r5-egress/bin/iron-proxy; \
    /opt/r5-egress/bin/iron-proxy --version

COPY broker_entrypoint.py /opt/r5-egress/broker_entrypoint.py
COPY egress_policy.json /opt/r5-egress/egress_policy.json
COPY broker_contract.json /opt/r5-egress/broker_contract.json
RUN sed -i 's/\r$//' /opt/r5-egress/broker_entrypoint.py \
    && chmod 0755 /opt/r5-egress/broker_entrypoint.py \
    && mkdir -p /opt/r5-egress/state /opt/r5-egress/ca-pub

ARG R5_EGRESS_CONTRACT_SHA256
ARG R5_EGRESS_POLICY_SHA256
ARG R5_SOURCE_GIT_SHA=""
LABEL io.powerunits.r5.egress-contract-sha256="${R5_EGRESS_CONTRACT_SHA256}" \
      io.powerunits.r5.egress-policy-sha256="${R5_EGRESS_POLICY_SHA256}" \
      io.powerunits.r5.hermes-base-digest="sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09" \
      io.powerunits.r5.iron-proxy-version="${IRON_PROXY_VERSION}" \
      io.powerunits.r5.iron-proxy-sha256="${IRON_PROXY_SHA256}" \
      io.powerunits.r5.source-git-sha="${R5_SOURCE_GIT_SHA}"

WORKDIR /opt/r5-egress
ENTRYPOINT ["/opt/hermes/.venv/bin/python", "/opt/r5-egress/broker_entrypoint.py"]

# Developer-Hermes DX image. Sandbox infrastructure, not Hermes core.
# FROM the pinned digest only — never a floating tag.
FROM nousresearch/hermes-agent@sha256:3811ed13da874fba2ac99b6d492db9a203d34cb6dccf90d886948c00d0ccec09

USER root

# The pinned image already ships Node/npm, Python, uv, Git, and Hermes.
# Pin TypeScript and pytest at image build. Do not resolve pytest from
# the network on every test execution.
RUN npm install -g typescript@7.0.2 \
    && uv pip install --python /opt/hermes/.venv/bin/python pytest==9.1.1 \
    && printf '%s\n' '#!/bin/sh' 'exec /opt/hermes/.venv/bin/python -m pytest "$@"' > /usr/local/bin/pytest \
    && chmod 0755 /usr/local/bin/pytest \
    && mkdir -p /opt/r5-developer /opt/data \
    && chown hermes:hermes /opt/data \
    && chmod 0775 /opt/data

COPY entrypoint.sh /opt/r5-developer/entrypoint.sh
COPY seed_home.py /opt/r5-developer/seed_home.py
COPY migrate_home.py /opt/r5-developer/migrate_home.py
COPY telegram_ops.py /opt/r5-developer/telegram_ops.py
COPY profiles/telegram-ops /opt/r5-developer/profiles/telegram-ops
COPY skills/r5-dev-skill /opt/r5-developer/skills/r5-dev-skill
COPY image_inputs/build_contract.json /opt/r5-developer/image_inputs/build_contract.json
RUN sed -i 's/\r$//' /opt/r5-developer/entrypoint.sh \
    && sed -i 's/\r$//' /opt/r5-developer/migrate_home.py \
    && chmod 0755 /opt/r5-developer/entrypoint.sh /opt/r5-developer/migrate_home.py \
    && chown -R hermes:hermes /opt/r5-developer

# Identity labels are applied last so a fingerprint-only rebuild does not
# invalidate the pinned TypeScript / pytest layer.
ARG R5_INPUT_SHA256
ARG R5_HERMES_BASE_DIGEST
ARG R5_CONTRACT_VERSION
ARG R5_SOURCE_GIT_SHA=""
LABEL io.powerunits.r5.input-sha256="${R5_INPUT_SHA256}" \
      io.powerunits.r5.hermes-base-digest="${R5_HERMES_BASE_DIGEST}" \
      io.powerunits.r5.contract-version="${R5_CONTRACT_VERSION}" \
      io.powerunits.r5.source-git-sha="${R5_SOURCE_GIT_SHA}"

# Runtime identity is hermes / 10000:10000. Root-only build steps above
# must restore this user. Do not leave the image as USER root.
# Windows bind-mount .git metadata created by a previous root runtime may
# remain root-owned; that does not justify a root Hermes process.
USER hermes
WORKDIR /workspace
ENTRYPOINT ["/opt/r5-developer/entrypoint.sh"]
CMD ["sleep", "infinity"]

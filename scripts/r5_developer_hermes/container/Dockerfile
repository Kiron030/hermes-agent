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
COPY skills/r5-dev-skill /opt/r5-developer/skills/r5-dev-skill
RUN sed -i 's/\r$//' /opt/r5-developer/entrypoint.sh \
    && chmod 0755 /opt/r5-developer/entrypoint.sh \
    && chown -R hermes:hermes /opt/r5-developer

# Runtime user is root inside an unprivileged container. Windows bind-mount
# `.git/objects` is not writable by uid 10000; local Git commits require this.
USER root
WORKDIR /workspace
ENTRYPOINT ["/opt/r5-developer/entrypoint.sh"]
CMD ["sleep", "infinity"]

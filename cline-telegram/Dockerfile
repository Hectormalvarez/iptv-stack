# Cline <-> Telegram bridge.
# Runs `cline connect telegram` against the repo workspace so Telegram messages
# become headless Cline sessions (remote control + debugging of the stack).
FROM node:24-slim

# Slim images lack the CA bundle; Telegram and provider TLS need it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Pin to the version validated on the host (3.0.74).
RUN npm install -g cline@3.0.74

COPY --chmod=755 entrypoint.sh /usr/local/bin/entrypoint.sh

# Run as the image's built-in non-root `node` user (uid 1000 = host hadev).
USER node
WORKDIR /workspace

# TELEGRAM_BOT_TOKEN / TELEGRAM_USER_ID come from .env via compose.
# entrypoint.sh seeds a writable cline config in /state from the read-only
# host ~/.cline mount, then bridges Telegram into headless sessions with
# cwd=/workspace (the repo, mounted RW).
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]

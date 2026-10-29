# ============================================================================
# ZERO-TOUCH SOCIAL AUTOMATION - PRODUCTION DOCKERFILE (RENDER & VPS READY)
# ============================================================================
FROM n8nio/n8n:1.76.1

USER root

# Copy crash-resilient entrypoint wrapper and strip Windows CRLF if present
COPY config/docker/entrypoint-wrapper.sh /usr/local/bin/entrypoint-wrapper.sh
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint-wrapper.sh && \
    chmod +x /usr/local/bin/entrypoint-wrapper.sh && \
    mkdir -p /files/media && \
    chown -R node:node /files/media

USER node

# Expose standard n8n port
EXPOSE 5678

# Built-in container healthcheck for automatic crash recovery
HEALTHCHECK --interval=30s --timeout=10s --start-period=45s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:${N8N_PORT:-5678}/healthz || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint-wrapper.sh"]
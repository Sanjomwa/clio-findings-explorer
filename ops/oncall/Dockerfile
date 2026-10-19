FROM python:3.12-slim

# The on-call webhook receiver: standard library only, nothing to install.
# Built with ops/oncall as the context. It runs as a non-root user with a read-only root
# filesystem; the only writable path is the inbox mount (see docker-compose.yml).
ENV PYTHONUNBUFFERED=1 \
    ONCALL_INBOX=/inbox

COPY receiver.py /app/receiver.py

USER 1000:1000
EXPOSE 8090
CMD ["python", "/app/receiver.py"]

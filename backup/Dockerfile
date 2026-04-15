FROM alpine:3.21.3 AS runtime

RUN apk add --no-cache \
    bash \
    curl \
    gzip \
    rclone \
    sqlite \
    tzdata

WORKDIR /backup

RUN adduser -D -s /bin/bash -u 1001 app

COPY backup.sh /usr/local/bin/backup.sh
RUN chmod +x /usr/local/bin/backup.sh

RUN mkdir -p /backup-status && chown app:app /backup-status

USER app

CMD ["/usr/local/bin/backup.sh"]

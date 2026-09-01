FROM teddysun/xray:latest

USER root

RUN apk add --no-cache \
        python3 \
        ca-certificates \
        curl \
        tzdata

WORKDIR /app

COPY converter.py /app/converter.py
COPY entrypoint.sh /app/entrypoint.sh

RUN chmod +x /app/entrypoint.sh

ENV SUBSCRIPTION_URL=""
ENV UPDATE_INTERVAL="3600"
ENV CONFIG_PATH="/etc/xray/config.json"
ENV DOWNLOAD_TIMEOUT="30"
ENV TZ="UTC"

ENTRYPOINT ["/app/entrypoint.sh"]
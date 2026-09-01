# Xray Subscription Updater

Docker image that automatically downloads a VLESS subscription, converts it to an Xray configuration, validates the generated configuration, and restarts Xray when the subscription changes.

The image is based on [`teddysun/xray:latest`](https://hub.docker.com/r/teddysun/xray).

## Features

- Based on `teddysun/xray:latest`
- Automatic subscription download
- Base64 subscription decoding
- VLESS URI parsing
- VLESS + XHTTP
- VLESS + WebSocket
- VLESS + gRPC
- TCP/RAW transport
- TLS
- Reality
- Automatic Xray configuration validation
- Atomic configuration replacement
- Automatic Xray restart after configuration changes
- Keeps the existing configuration if the subscription update fails
- Periodic subscription updates
- Multi-architecture Docker image:
  - `linux/amd64`
  - `linux/arm64`

## Docker image

Images are published to GitHub Container Registry (GHCR):

```text
ghcr.io/lanakod/xray-subscription-updater:latest
```

## Usage

```yaml
name: auto-xray

services:
  xray:
    image: ghcr.io/lanakod/xray-subscription-updater:latest
    container_name: xray-subscription
    restart: unless-stopped
    environment:
      SUBSCRIPTION_URL: "https://example.com/sub/a1b2c3d4"
      UPDATE_INTERVAL: "3600"
      DOWNLOAD_TIMEOUT: "30"
      TZ: "Europe/Moscow"
    ports:
      # Change these ports if you use different proxy ports.
      # Make sure the corresponding inbounds in your Xray subscription
      # listen on 0.0.0.0 or the required interface address, not 127.0.0.1.
      - "1080:1080"
      - "1081:1081"
    volumes:
      - ./xray-data:/etc/xray
```

The container provides:

- SOCKS5 proxy on `1080`
- HTTP proxy on `1081`

The generated Xray configuration is stored at:

```text
/etc/xray/config.json
```

The downloaded subscription is stored at:

```text
/etc/xray/subscription.txt
```

## Environment variables

| Variable           |                 Default | Description                               |
|--------------------|------------------------:|-------------------------------------------|
| `SUBSCRIPTION_URL` |                       — | URL of the VLESS subscription. Required.  |
| `UPDATE_INTERVAL`  |                  `3600` | Subscription update interval in seconds.  |
| `CONFIG_PATH`      | `/etc/xray/config.json` | Path to the generated Xray configuration. |
| `DOWNLOAD_TIMEOUT` |                    `30` | Subscription download timeout in seconds. |
| `TZ`               |                   `UTC` | Container timezone.                       |

## How it works

```text
VLESS Subscription
        │
        ▼
 Download subscription
        │
        ▼
 Decode Base64
        │
        ▼
 Parse VLESS URIs
        │
        ▼
 Generate Xray config
        │
        ▼
 Validate with Xray
        │
        ├── invalid ──► keep current config
        │
        ▼
 Compare with current config
        │
        ├── unchanged ─► continue
        │
        ▼
 Atomic config replacement
        │
        ▼
 Restart Xray
```

The first node in the subscription is used as the default outbound for incoming SOCKS/HTTP proxy traffic.

A `direct` outbound and a `block` outbound are also added automatically.

## Building locally

```bash
docker build -t auto-xray:latest .
```

Run:

```bash
docker run -d \
  --name xray-subscription \
  --restart unless-stopped \
  -e SUBSCRIPTION_URL="https://example.com/sub/a1b2c3d4" \
  -e UPDATE_INTERVAL="3600" \
  -e TZ="UTC" \
  -p 1080:1080 \
  -p 1081:1081 \
  -v "$(pwd)/xray-data:/etc/xray" \
  auto-xray:latest
```

## Multi-architecture build

The GitHub Actions workflow builds and publishes both:

```text
linux/amd64
linux/arm64
```

Docker Buildx creates a multi-platform manifest, so Docker automatically pulls the correct image for the host architecture.

## License

This project is licensed under the [MIT License](LICENSE.md).

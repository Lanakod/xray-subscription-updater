# Xray Subscription Updater

Docker image that automatically downloads a VLESS subscription, converts it to a Xray configuration, validates the generated configuration, and restarts Xray when the subscription changes.

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
- Remnawave HWID device identification
- Automatic container OS detection
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
      # Remnawave device identification
      DEVICE_NAME: "media-server"
      DEVICE_ID: "0123456789abcdef0123456789abcdef"
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

Start the container:

```bash
docker compose up -d
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

## Remnawave device identification

The updater can identify itself as a device when downloading a subscription from Remnawave.

The following HTTP headers are sent with every subscription request:

```text
x-hwid: <DEVICE_ID>
x-device-model: <DEVICE_NAME>
x-device-os: <detected container OS>
x-ver-os: <detected container OS version>
```

For example:

```text
x-hwid: 1ae4b7f8345d57f2cb6fec848252bb18
x-device-model: media-server
x-device-os: Alpine Linux
x-ver-os: 3.22.1
```

This allows the container to appear as a separate device in the Remnawave HWID device list.

### DEVICE_NAME

`DEVICE_NAME` is a human-readable name for the device.

Example:

```yaml
DEVICE_NAME: "media-server"
```

Other examples:

```yaml
DEVICE_NAME: "home-server"
```

```yaml
DEVICE_NAME: "nas"
```

```yaml
DEVICE_NAME: "orange-pi"
```

The value is sent to Remnawave as:

```text
x-device-model
```

### DEVICE_ID

`DEVICE_ID` is a stable unique identifier for the device.

Generate one before creating the container:

```bash
openssl rand -hex 16
```

Example output:

```text
1ae4b7f8345d57f2cb6fec848252bb18
```

Then add it to `compose.yaml`:

```yaml
DEVICE_ID: "1ae4b7f8345d57f2cb6fec848252bb18"
```

Do not regenerate `DEVICE_ID` when recreating or updating the container.

As long as the same `DEVICE_ID` is used, Remnawave will recognize subscription requests as coming from the same device.

If you generate a new `DEVICE_ID`, Remnawave will treat it as a new device.

### Automatic OS detection

The operating system and its version do not need to be configured in `compose.yaml`.

They are detected automatically from:

```text
/etc/os-release
```

inside the Docker container.

For an Alpine-based container this will typically produce:

```text
x-device-os: Alpine Linux
x-ver-os: 3.22.1
```

The detected values describe the environment where the subscription updater is actually running — the Docker container, not the Docker host.

This means that even if the container is running on Debian, Ubuntu, Windows, macOS, or another host operating system, Remnawave will see the container OS.

## Environment variables

| Variable           | Default                 | Description                                             |
|--------------------|-------------------------|---------------------------------------------------------|
| `SUBSCRIPTION_URL` | —                       | URL of the VLESS subscription. Required.                |
| `DEVICE_NAME`      | `xray-subscription`     | Device name sent to Remnawave as `x-device-model`.      |
| `DEVICE_ID`        | —                       | Stable device identifier sent to Remnawave as `x-hwid`. |
| `UPDATE_INTERVAL`  | `3600`                  | Subscription update interval in seconds.                |
| `CONFIG_PATH`      | `/etc/xray/config.json` | Path to the generated Xray configuration.               |
| `DOWNLOAD_TIMEOUT` | `30`                    | Subscription download timeout in seconds.               |
| `TZ`               | `UTC`                   | Container timezone.                                     |

`DEVICE_ID` should remain unchanged for the lifetime of the device.

Generate it with:

```bash
openssl rand -hex 16
```

## How it works

```text
 VLESS Subscription
         │
         ▼
 Send device information
         │
         ├── x-hwid
         ├── x-device-model
         ├── x-device-os
         └── x-ver-os
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

Build:

```bash
docker build -t auto-xray:latest .
```

Generate a device ID:

```bash
openssl rand -hex 16
```

Run:

```bash
docker run -d \
  --name xray-subscription \
  --restart unless-stopped \
  -e SUBSCRIPTION_URL="https://example.com/sub/a1b2c3d4" \
  -e DEVICE_NAME="media-server" \
  -e DEVICE_ID="1ae4b7f8345d57f2cb6fec848252bb18" \
  -e UPDATE_INTERVAL="3600" \
  -e TZ="UTC" \
  -p 1080:1080 \
  -p 1081:1081 \
  -v "$(pwd)/xray-data:/etc/xray" \
  auto-xray:latest

## Multi-architecture build

The GitHub Actions workflow builds and publishes both:

```text
linux/amd64
linux/arm64
```

Docker Buildx creates a multi-platform manifest, so Docker automatically pulls the correct image for the host architecture.

## License

This project is licensed under the [MIT License](LICENSE.md).

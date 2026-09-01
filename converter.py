#!/usr/bin/env python3

import sys
import json
import base64
import urllib.parse
import re


def decode_base64(data: str) -> str:
    """
    Decode subscription Base64.

    Supports:
    - standard Base64
    - URL-safe Base64
    - missing padding
    - newlines/spaces
    """

    data = data.strip()

    # Remove whitespace/newlines from subscription
    data = re.sub(r"\s+", "", data)

    # Add missing padding
    data += "=" * (-len(data) % 4)

    try:
        decoded = base64.b64decode(data, validate=False)
        return decoded.decode("utf-8")

    except Exception:
        try:
            decoded = base64.urlsafe_b64decode(data)
            return decoded.decode("utf-8")
        except Exception as exc:
            raise ValueError(
                f"Unable to decode subscription Base64: {exc}"
            )


def parse_vless_uri(uri: str, index: int) -> dict:
    """
    Convert:

    vless://UUID@host:443?...#TAG

    into Xray outbound configuration.
    """

    uri = uri.strip()

    if not uri:
        raise ValueError("Empty VLESS URI")

    if not uri.lower().startswith("vless://"):
        raise ValueError(f"Unsupported URI: {uri[:50]}")

    parsed = urllib.parse.urlsplit(uri)

    if not parsed.hostname:
        raise ValueError(f"VLESS URI has no hostname: {uri}")

    if not parsed.username:
        raise ValueError(f"VLESS URI has no UUID: {uri}")

    uuid = urllib.parse.unquote(parsed.username)
    address = parsed.hostname
    port = parsed.port or 443

    params = urllib.parse.parse_qs(
        parsed.query,
        keep_blank_values=True,
    )

    def get_param(name, default=None):
        values = params.get(name)

        if not values:
            return default

        return values[0]

    #
    # Fragment / node name
    #

    tag = urllib.parse.unquote(parsed.fragment)

    if not tag:
        tag = f"node-{index:02d}"

    #
    # VLESS settings
    #

    user = {
        "id": uuid,
        "encryption": get_param("encryption", "none"),
    }

    flow = get_param("flow")

    if flow:
        user["flow"] = flow

    #
    # Outbound
    #

    outbound = {
        "tag": tag,
        "protocol": "vless",

        "settings": {
            "vnext": [
                {
                    "address": address,
                    "port": port,
                    "users": [
                        user
                    ]
                }
            ]
        }
    }

    #
    # Transport
    #

    transport_type = get_param("type")

    if not transport_type:
        transport_type = get_param("network", "tcp")

    transport_type = transport_type.lower()

    stream_settings = {}

    #
    # XHTTP
    #

    if transport_type == "xhttp":

        stream_settings["method"] = "xhttp"

        xhttp_settings = {}

        path = get_param("path")

        if path:
            xhttp_settings["path"] = urllib.parse.unquote(path)

        host = get_param("host")

        if host:
            xhttp_settings["host"] = urllib.parse.unquote(host)

        mode = get_param("mode")

        if mode:
            xhttp_settings["mode"] = mode

        #
        # XHTTP extra
        #
        # Example:
        #
        # extra=%7B%22headers%22%3A%7B%22Referer%22...
        #

        extra = get_param("extra")

        if extra:
            extra = urllib.parse.unquote(extra)

            try:
                extra_json = json.loads(extra)

                if not isinstance(extra_json, dict):
                    raise ValueError("extra is not a JSON object")

                xhttp_settings["extra"] = extra_json

            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Invalid XHTTP extra JSON: {exc}"
                )

        stream_settings["xhttpSettings"] = xhttp_settings

    #
    # WebSocket
    #

    elif transport_type in ("ws", "websocket"):

        stream_settings["network"] = "ws"

        ws_settings = {}

        path = get_param("path")

        if path:
            ws_settings["path"] = urllib.parse.unquote(path)

        host = get_param("host")

        if host:
            ws_settings["headers"] = {
                "Host": urllib.parse.unquote(host)
            }

        stream_settings["wsSettings"] = ws_settings

    #
    # gRPC
    #

    elif transport_type == "grpc":

        stream_settings["network"] = "grpc"

        service_name = get_param("serviceName")

        if service_name:
            stream_settings["grpcSettings"] = {
                "serviceName": service_name
            }
        else:
            stream_settings["grpcSettings"] = {}

    #
    # TCP / RAW
    #

    else:

        stream_settings["method"] = "raw"

        stream_settings["rawSettings"] = {}

    #
    # Security
    #

    security = get_param("security", "none")

    if security:
        security = security.lower()

    stream_settings["security"] = security

    #
    # REALITY
    #

    if security == "reality":

        reality_settings = {}

        sni = get_param("sni")

        if sni:
            reality_settings["serverName"] = sni

        fingerprint = get_param("fp")

        if fingerprint:
            reality_settings["fingerprint"] = fingerprint

        #
        # Current Xray calls this "password".
        #
        # Remnawave/VLESS links commonly expose it as pbk.
        #

        public_key = get_param("pbk")

        if public_key:
            reality_settings["password"] = public_key

        short_id = get_param("sid")

        if short_id:
            reality_settings["shortId"] = short_id

        #
        # SpiderX is sometimes supplied as spx.
        #

        spider_x = get_param("spx")

        if spider_x:
            reality_settings["spiderX"] = spider_x

        stream_settings["realitySettings"] = reality_settings

    #
    # TLS
    #

    elif security == "tls":

        tls_settings = {}

        sni = get_param("sni")

        if sni:
            tls_settings["serverName"] = sni

        fingerprint = get_param("fp")

        if fingerprint:
            tls_settings["fingerprint"] = fingerprint

        stream_settings["tlsSettings"] = tls_settings

    outbound["streamSettings"] = stream_settings

    return outbound


def parse_subscription(data: str) -> list[dict]:
    """
    Parse decoded subscription.

    Expected:

    vless://...
    vless://...
    vless://...
    """

    lines = data.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    links = []

    for line in lines:

        line = line.strip()

        if not line:
            continue

        if line.startswith("vless://"):
            links.append(line)

    if not links:
        raise ValueError(
            "No VLESS links found in subscription"
        )

    outbounds = []

    for index, link in enumerate(links, start=1):

        try:
            outbound = parse_vless_uri(
                link,
                index,
            )

            outbounds.append(outbound)

        except Exception as exc:

            print(
                f"WARNING: Failed to parse VLESS #{index}: {exc}",
                file=sys.stderr,
            )

    if not outbounds:
        raise ValueError(
            "No valid VLESS outbounds found"
        )

    return outbounds


def generate_config(subscription: str) -> dict:

    decoded = decode_base64(subscription)

    print(
        f"[converter] Decoded subscription: "
        f"{len(decoded)} bytes",
        file=sys.stderr,
    )

    outbounds = parse_subscription(decoded)

    print(
        f"[converter] Found {len(outbounds)} VLESS nodes",
        file=sys.stderr,
    )

    #
    # First node is the default proxy.
    #

    first_tag = outbounds[0]["tag"]

    #
    # Add direct outbound.
    #

    outbounds.append(
        {
            "tag": "direct",
            "protocol": "freedom",
            "settings": {}
        }
    )

    #
    # Add block outbound.
    #

    outbounds.append(
        {
            "tag": "block",
            "protocol": "blackhole",
            "settings": {}
        }
    )

    #
    # Local SOCKS proxy
    #

    config = {
        "log": {
            "loglevel": "warning"
        },

        "inbounds": [
            {
                "tag": "socks-in",
                "listen": "0.0.0.0",
                "port": 1080,
                "protocol": "socks",

                "settings": {
                    "auth": "noauth",
                    "udp": True
                }
            },

            {
                "tag": "http-in",
                "listen": "0.0.0.0",
                "port": 1081,
                "protocol": "http",

                "settings": {}
            }
        ],

        "outbounds": outbounds,

        "routing": {
            "domainStrategy": "IPIfNonMatch",

            "rules": [
                {
                    "type": "field",
                    "inboundTag": [
                        "socks-in",
                        "http-in"
                    ],
                    "outboundTag": first_tag
                }
            ]
        }
    }

    return config


def main():

    if len(sys.argv) != 2:
        print(
            f"Usage: {sys.argv[0]} <subscription-file>",
            file=sys.stderr,
        )
        sys.exit(1)

    subscription_file = sys.argv[1]

    try:

        with open(
            subscription_file,
            "r",
            encoding="utf-8",
        ) as file:

            subscription = file.read()

        config = generate_config(subscription)

        print(
            json.dumps(
                config,
                ensure_ascii=False,
                indent=2,
            )
        )

    except Exception as exc:

        print(
            f"[converter] ERROR: {exc}",
            file=sys.stderr,
        )

        sys.exit(1)


if __name__ == "__main__":
    main()
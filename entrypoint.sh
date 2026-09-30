#!/bin/sh

set -eu

SUBSCRIPTION_URL="${SUBSCRIPTION_URL:-}"
UPDATE_INTERVAL="${UPDATE_INTERVAL:-3600}"
CONFIG_PATH="${CONFIG_PATH:-/etc/xray/config.json}"
DOWNLOAD_TIMEOUT="${DOWNLOAD_TIMEOUT:-30}"

DEVICE_NAME="${DEVICE_NAME:-xray-subscription}"
DEVICE_ID="${DEVICE_ID:-}"

DEVICE_OS="Linux"
DEVICE_OS_VERSION="unknown"

if [ -r /etc/os-release ]; then
    DEVICE_OS="$(
        . /etc/os-release
        printf '%s' "${NAME:-Linux}"
    )"

    DEVICE_OS_VERSION="$(
        . /etc/os-release
        printf '%s' "${VERSION_ID:-unknown}"
    )"
fi

CONFIG_DIR="$(dirname "$CONFIG_PATH")"

SUBSCRIPTION_FILE="${CONFIG_DIR}/subscription.txt"
NEW_CONFIG="${CONFIG_DIR}/config.new.json"
BACKUP_CONFIG="${CONFIG_PATH}.bak"

XRAY_BIN="/usr/bin/xray"
CONVERTER="/app/converter.py"

XRAY_PID=""

log() {
    echo "[xray-subscription] $*"
}

die() {
    log "ERROR: $*"
    exit 1
}

#
# Check environment
#

if [ -z "$SUBSCRIPTION_URL" ]; then
    die "SUBSCRIPTION_URL is not set"
fi

if [ -z "$DEVICE_ID" ]; then
    echo "ERROR: DEVICE_ID is not set."
    echo "Generate one with: openssl rand -hex 16"
    exit 1
fi

mkdir -p "$CONFIG_DIR"

#
# Download subscription
#

download_subscription() {

    log "Downloading subscription..."

    rm -f "$SUBSCRIPTION_FILE"

    if ! curl \
        --fail \
        --silent \
        --show-error \
        --location \
        --max-time "$DOWNLOAD_TIMEOUT" \
        --retry 3 \
        --retry-delay 5 \
        --header "Accept: application/json" \
        --header "User-Agent: xray-subscription/1.0" \
        --header "x-hwid: $DEVICE_ID" \
        --header "x-device-model: $DEVICE_NAME" \
        --header "x-device-os: $DEVICE_OS" \
        --header "x-ver-os: $DEVICE_OS_VERSION" \
        "$SUBSCRIPTION_URL" \
        --output "$SUBSCRIPTION_FILE"; then

        log "Failed to download subscription"

        rm -f "$SUBSCRIPTION_FILE"

        return 1
    fi

    if [ ! -s "$SUBSCRIPTION_FILE" ]; then

        log "Subscription response is empty"

        rm -f "$SUBSCRIPTION_FILE"

        return 1
    fi

    log "Subscription downloaded"

    return 0
}

#
# Convert subscription to Xray config
#

generate_config() {

    log "Converting subscription to Xray configuration..."

    rm -f "$NEW_CONFIG"

    if ! python3 \
        "$CONVERTER" \
        "$SUBSCRIPTION_FILE" \
        > "$NEW_CONFIG"; then

        log "Failed to convert subscription"

        rm -f "$NEW_CONFIG"

        return 1
    fi

    if [ ! -s "$NEW_CONFIG" ]; then

        log "Generated configuration is empty"

        rm -f "$NEW_CONFIG"

        return 1
    fi

    log "Xray configuration generated"

    return 0
}

#
# Validate Xray config
#

validate_config() {

    log "Testing Xray configuration..."

    if ! "$XRAY_BIN" run \
        -format json \
        -test \
        -config "$NEW_CONFIG"; then

        log "Xray configuration validation FAILED"

        return 1
    fi

    log "Xray configuration is valid"

    return 0
}

#
# Check whether config changed
#

config_changed() {

    if [ ! -f "$CONFIG_PATH" ]; then
        return 0
    fi

    if cmp -s "$NEW_CONFIG" "$CONFIG_PATH"; then
        return 1
    fi

    return 0
}

#
# Install config
#

install_config() {

    log "Installing new Xray configuration..."

    if [ -f "$CONFIG_PATH" ]; then

        cp \
            "$CONFIG_PATH" \
            "$BACKUP_CONFIG"

    fi

    #
    # Atomic replacement
    #

    mv \
        "$NEW_CONFIG" \
        "$CONFIG_PATH"

    log "Configuration installed"
}

#
# Start Xray
#

start_xray() {

    log "Starting Xray..."

    "$XRAY_BIN" run \
        -format json \
        -config "$CONFIG_PATH" &

    XRAY_PID=$!

    log "Xray started (PID: $XRAY_PID)"
}

#
# Stop Xray
#

stop_xray() {

    if [ -n "${XRAY_PID:-}" ] &&
       kill -0 "$XRAY_PID" 2>/dev/null; then

        log "Stopping Xray..."

        kill "$XRAY_PID" 2>/dev/null || true

        wait "$XRAY_PID" 2>/dev/null || true

        XRAY_PID=""

    fi
}

#
# Restart Xray
#

restart_xray() {

    stop_xray

    start_xray
}

#
# Full subscription update
#

update_subscription() {

    if ! download_subscription; then
        return 1
    fi

    if ! generate_config; then
        return 1
    fi

    if ! validate_config; then
        rm -f "$NEW_CONFIG"
        return 1
    fi

    if ! config_changed; then

        log "Configuration has not changed"

        rm -f "$NEW_CONFIG"

        return 2
    fi

    install_config

    return 0
}

#
# Cleanup
#

cleanup() {

    log "Stopping..."

    stop_xray

    rm -f "$NEW_CONFIG"

    exit 0
}

trap cleanup INT TERM HUP

#
# Initial configuration
#

log "========================================"
log "Xray Subscription Updater"
log "========================================"

log "Subscription: $SUBSCRIPTION_URL"
log "Update interval: ${UPDATE_INTERVAL}s"
log "Config: $CONFIG_PATH"

#
# If config doesn't exist, initial download is mandatory.
#

if [ ! -f "$CONFIG_PATH" ]; then

    log "No existing Xray configuration"

    if ! update_subscription; then

        log "Initial subscription update failed"

        die "Unable to create Xray configuration"

    fi

else

    log "Existing Xray configuration found"

    #
    # Try to update immediately.
    # Existing config remains valid if subscription fails.
    #

    update_subscription || {

        RESULT=$?

        case "$RESULT" in

            1)
                log "Initial subscription update failed"
                log "Keeping existing configuration"
                ;;

            2)
                log "Existing configuration is already up-to-date"
                ;;

            *)
                log "Subscription update returned code $RESULT"
                ;;

        esac
    }

fi

#
# Make sure config exists.
#

if [ ! -f "$CONFIG_PATH" ]; then
    die "Xray configuration does not exist"
fi

#
# Start Xray
#

start_xray

#
# Main update loop
#

while true; do

    log "Next update in ${UPDATE_INTERVAL}s"

    sleep "$UPDATE_INTERVAL"

    #
    # Check Xray process
    #

    if ! kill -0 "$XRAY_PID" 2>/dev/null; then

        log "Xray process is not running"

        start_xray

    fi

    #
    # Update subscription
    #

    log "Checking subscription..."

    update_subscription

    RESULT=$?

    case "$RESULT" in

        0)

            log "New configuration installed"

            restart_xray

            ;;

        1)

            log "Subscription update failed"
            log "Keeping current configuration"

            ;;

        2)

            log "No changes detected"

            ;;

        *)

            log "Unknown update result: $RESULT"

            ;;

    esac

done
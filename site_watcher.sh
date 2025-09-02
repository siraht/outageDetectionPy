#!/bin/bash

#==============================================================================
# Multi-Site Outage Watcher & Snapshot Trigger
#
# Reads a config file to monitor multiple sites. When a site recovers from
# downtime, it triggers the outage_snapshot.py script to collect data.
#==============================================================================

# --- CONFIGURATION ---
# The path to the file containing the list of sites to monitor.
SITES_CONFIG_FILE="/root/outageDetectionPy/watcher_sites.conf"

# The full path to your Python snapshot script.
PYTHON_SCRIPT_PATH="/root/outageDetectionPy/outage_snapshot.py"

# --- SCRIPT LOGIC ---

# Check if the config file exists
if [ ! -f "$SITES_CONFIG_FILE" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR: Site config file not found at $SITES_CONFIG_FILE"
    exit 1
fi

# Function to write messages to a specific log file with a timestamp.
log() {
    local app_name="$1"
    local message="$2"
    local log_file="/home/runcloud/logs/watcher_${app_name}.log"
    # Create log directory if it doesn't exist
    mkdir -p "$(dirname "$log_file")"
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $message" >> "$log_file"
}

# Read the config file line by line
while read -r APP_NAME PHP_VERSION APP_PATH SITE_URL; do
    # Skip empty lines or comments
    [[ -z "$APP_NAME" || "$APP_NAME" =~ ^# ]] && continue

    # Define unique state file for this app
    STATE_FILE="/tmp/${APP_NAME}_outage_state.lock"

    # Check the site's HTTP status code
    HTTP_STATUS=$(curl -L -s -o /dev/null -w "%{http_code}" --connect-timeout 10 "$SITE_URL")

    if [[ "$HTTP_STATUS" -ge 200 && "$HTTP_STATUS" -lt 400 ]]; then
        # --- SITE IS UP ---
        if [ -f "$STATE_FILE" ]; then
            log "$APP_NAME" "✅ Site is UP (Status: $HTTP_STATUS). Outage has ended."

            START_TIME_STR=$(cat "$STATE_FILE")
            END_TIME_STR=$(date '+%Y-%m-%d %H:%M:%S')

            log "$APP_NAME" "   - Outage Start: $START_TIME_STR"
            log "$APP_NAME" "   - Outage End:   $END_TIME_STR"
            log "$APP_NAME" "   - Triggering Python snapshot script..."

            # Run the Python script with all necessary arguments, including the new --app-path
            python3 "$PYTHON_SCRIPT_PATH" \
                --app-name "$APP_NAME" \
                --start "$START_TIME_STR" \
                --end "$END_TIME_STR" \
                --php-version "$PHP_VERSION" \
                --app-path "$APP_PATH" >> "/home/runcloud/logs/watcher_${APP_NAME}.log" 2>&1

            rm "$STATE_FILE"
            log "$APP_NAME" "   - Snapshot complete. State file removed."
        fi
    else
        # --- SITE IS DOWN ---
        if [ ! -f "$STATE_FILE" ]; then
            log "$APP_NAME" "❌ Site is DOWN (Status: $HTTP_STATUS). Creating state file."
            date '+%Y-%m-%d %H:%M:%S' > "$STATE_FILE"
        fi
    fi
done < "$SITES_CONFIG_FILE"

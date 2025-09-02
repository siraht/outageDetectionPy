#!/bin/bash

#==============================================================================
# Multi-Site Outage Watcher & Snapshot Trigger
#
# Reads a config file to monitor multiple sites. When a site recovers from
# downtime, it triggers the outage_snapshot.py script to collect data.
# Logs all activities to /home/runcloud/outage_reports/shcron.log
#==============================================================================

# --- CONFIGURATION ---
# The path to the file containing the list of sites to monitor.
SITES_CONFIG_FILE="$(dirname "$0")/watcher_sites.conf"

# The full path to your Python snapshot script.
PYTHON_SCRIPT_PATH="$(dirname "$0")/outage_snapshot.py"

# Main log file for script execution
MAIN_LOG_FILE="/home/runcloud/outage_reports/shcron.log"

# Ensure log directory exists
mkdir -p "$(dirname "$MAIN_LOG_FILE")"

# Function to write messages to both the main log and app-specific log
log() {
    local app_name="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Log to main log file
    echo "$timestamp - [$app_name] $message" >> "$MAIN_LOG_FILE"
    
    # Also log to app-specific log file if app_name is provided
    if [[ -n "$app_name" && "$app_name" != "SCRIPT" ]]; then
        local app_log_file="/home/runcloud/logs/watcher_${app_name}.log"
        mkdir -p "$(dirname "$app_log_file")"
        echo "$timestamp - $message" >> "$app_log_file"
    fi
}

# Log script start
log "SCRIPT" "Starting site watcher script"
log "SCRIPT" "Using config file: $SITES_CONFIG_FILE"

# Check if the config file exists
if [ ! -f "$SITES_CONFIG_FILE" ]; then
    log "SCRIPT" "ERROR: Site config file not found at $SITES_CONFIG_FILE"
    exit 1
fi

# Read the config file line by line
while read -r APP_NAME PHP_VERSION APP_PATH SITE_URL; do
    # Skip empty lines or comments
    [[ -z "$APP_NAME" || "$APP_NAME" =~ ^# ]] && continue
    
    log "$APP_NAME" "Checking site availability: $SITE_URL"
    
    # Define unique state file for this app
    STATE_FILE="/tmp/${APP_NAME}_outage_state.lock"

    # Check the site's HTTP status code
    HTTP_STATUS=$(curl -L -s -o /dev/null -w "%{http_code}" --connect-timeout 10 "$SITE_URL" 2>&1)
    CURL_EXIT_CODE=$?

    if [[ $CURL_EXIT_CODE -ne 0 ]]; then
        log "$APP_NAME" "ERROR: Curl failed with exit code $CURL_EXIT_CODE: $HTTP_STATUS"
        continue
    fi

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
        log "$APP_NAME" "❌ Site is DOWN or unreachable (Status: $HTTP_STATUS)"
        if [ ! -f "$STATE_FILE" ]; then
            log "$APP_NAME" "❌ Site is DOWN (Status: $HTTP_STATUS). Creating state file."
            date '+%Y-%m-%d %H:%M:%S' > "$STATE_FILE"
        fi
    fi

done < "$SITES_CONFIG_FILE"

log "SCRIPT" "Site watcher script completed"

# Outage Detection System

A comprehensive multi-site outage detection and snapshot system for web applications. This system monitors multiple websites and automatically collects detailed diagnostic information when outages are detected and resolved.

## Features

- **Multi-site monitoring**: Monitor multiple websites from a single configuration file
- **Automated outage detection**: Continuously monitors HTTP status codes
- **Enhanced snapshot collection**: Automatically captures system state during outages including:
  - System performance data (CPU, memory, load average) using `sar`
  - Application logs (nginx access/error, PHP-FPM slow logs)
  - Configuration files (nginx and PHP-FPM configs)
  - **File modification tracking**: Identifies and copies all files modified during outage windows
- **Structured reporting**: Generates timestamped reports with JSON summaries
- **Logging**: Per-site logging with timestamps for audit trails

## Requirements

- Linux system (tested on Ubuntu)
- Python 3.6+
- `curl` for HTTP monitoring
- `sysstat` package for system performance data
- `find` command for file modification tracking

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/siraht/outageDetectionPy.git
   cd outageDetectionPy
   ```

2. **Install required system packages**:
   ```bash
   sudo apt update
   sudo apt install -y sysstat curl
   ```

3. **Make scripts executable**:
   ```bash
   chmod +x site_watcher.sh outage_snapshot.py
   ```

4. **Create configuration file**:
   ```bash
   cp watcher_sites.conf.example watcher_sites.conf
   ```

5. **Create necessary directories**:
   ```bash
   sudo mkdir -p /home/runcloud/logs /home/runcloud/outage_reports
   ```

## Configuration

### Site Configuration

Edit `watcher_sites.conf` to define your sites to monitor. Each line should contain four space-separated values:

```
AppName PHPVersion WebAppPath URL
```

**Example**:
```
my-website 8.1 /home/runcloud/webapps/my-website https://my-website.com
api-service 8.2 /home/runcloud/webapps/api-service https://api.my-website.com
blog-site 7.4 /home/runcloud/webapps/blog-site https://blog.my-website.com
```

**Parameters**:
- `AppName`: Unique identifier for the application (used in logs and reports)
- `PHPVersion`: PHP version used by the application (for finding PHP-FPM logs)
- `WebAppPath`: Absolute path to the application's root directory
- `URL`: Full URL to monitor (including protocol)

### Directory Structure

The system expects the following directory structure (customizable in scripts):

```
/home/runcloud/
├── logs/                           # Application logs
├── outage_reports/                 # Generated outage reports
└── webapps/                        # Web applications
    ├── my-website/
    ├── api-service/
    └── blog-site/
```

## Usage

### Manual Execution

Test the system manually:

```bash
# Test site monitoring (run once)
./site_watcher.sh

# Test snapshot collection directly
./outage_snapshot.py --app-name my-website \
                     --start "2025-01-01 10:00:00" \
                     --end "2025-01-01 10:30:00" \
                     --php-version 8.1 \
                     --app-path /home/runcloud/webapps/my-website
```

### Automated Monitoring

Set up automated monitoring using cron:

```bash
# Edit crontab
crontab -e

# Add line to run every minute
* * * * * /path/to/outageDetectionPy/site_watcher.sh

# Or run every 5 minutes
*/5 * * * * /path/to/outageDetectionPy/site_watcher.sh
```

## How It Works

### Monitoring Process

1. **Site Check**: The `site_watcher.sh` script checks each configured site's HTTP status
2. **Outage Detection**: When a site returns non-2xx/3xx status, an outage is recorded
3. **State Tracking**: Outage start time is saved in a temporary state file
4. **Recovery Detection**: When site returns to healthy status, recovery is detected
5. **Snapshot Trigger**: The Python snapshot script is automatically executed
6. **Data Collection**: System collects logs, performance data, configs, and modified files
7. **Report Generation**: A comprehensive report is generated with all collected data

### Data Collection

When an outage ends, the system collects:

#### System Performance Data
- **CPU Usage**: Historical CPU utilization during outage window
- **Memory Usage**: Memory consumption patterns
- **Load Average**: System load metrics

#### Application Logs
- **Nginx Access Logs**: HTTP requests during outage period
- **Nginx Error Logs**: Server errors and warnings
- **PHP-FPM Slow Logs**: Slow PHP processes (if enabled)

#### Configuration Files
- **Nginx Configuration**: Site-specific nginx config
- **PHP-FPM Configuration**: Application pool configuration

#### File Modifications
- **Modified Files**: All files changed during outage window
- **Directory Structure**: Preserved directory hierarchy
- **Manifest**: Detailed list of all copied files

## Output Structure

Reports are generated in `/home/runcloud/outage_reports/` with the following structure:

```
/home/runcloud/outage_reports/
└── my-website_20250101_100000/
    ├── summary.json                    # Complete report summary
    ├── nginx_access.slice.log          # Nginx access logs
    ├── nginx_error.slice.log           # Nginx error logs  
    ├── php_fpm_slow.slice.log          # PHP-FPM slow logs
    ├── sar_cpu_usage.txt               # CPU performance data
    ├── sar_memory_usage.txt            # Memory performance data
    ├── sar_load_average.txt            # Load average data
    ├── my-website.conf                 # Nginx config (if found)
    ├── my-website.conf                 # PHP-FPM config (if found)
    ├── modified_files_manifest.txt     # List of modified files
    └── modified_files/                 # Directory containing modified files
        └── [preserved directory structure]
```

## Customization

### Paths and Directories

You can customize default paths by editing the Python script constants:

```python
DEFAULT_OUTPUT_DIR = Path("/home/runcloud/outage_reports")
DEFAULT_LOG_DIR = Path("/home/runcloud/logs")
DEFAULT_NGINX_CONF_DIR = Path("/etc/nginx-rc/conf.d")
DEFAULT_PHP_CONF_BASE = Path("/etc/php-rc")
```

### Log Formats

To support different log formats, modify the log parsing configuration in `outage_snapshot.py`:

```python
logs_to_collect = {
    "nginx_access": {
        "path": args.log_dir / f"{args.app_name}_nginx_access.log",
        "regex": r'\[(.*?)\]',
        "format": '%d/%b/%Y:%H:%M:%S %z'
    },
    # Add more log types as needed
}
```

### Monitoring Frequency

Adjust the cron schedule based on your needs:
- **High frequency**: `* * * * *` (every minute)
- **Standard**: `*/5 * * * *` (every 5 minutes)
- **Low frequency**: `*/15 * * * *` (every 15 minutes)

## Troubleshooting

### Common Issues

1. **Permission Denied**:
   ```bash
   sudo chown -R $(whoami):$(whoami) /path/to/outageDetectionPy
   chmod +x site_watcher.sh outage_snapshot.py
   ```

2. **Missing Directories**:
   ```bash
   sudo mkdir -p /home/runcloud/logs /home/runcloud/outage_reports
   sudo chown -R runcloud:runcloud /home/runcloud/
   ```

3. **No System Data**:
   - Ensure `sysstat` is installed: `sudo apt install sysstat`
   - Enable data collection: `sudo systemctl enable sysstat`

4. **Python Dependencies**:
   - Ensure Python 3.6+ is installed
   - Check if required modules are available

### Debugging

Enable verbose logging by modifying the scripts:

```bash
# Add debug output to site_watcher.sh
set -x  # Add at the top of the script

# Run Python script with verbose output
python3 -v outage_snapshot.py [arguments]
```

## Security Considerations

- **Configuration File**: The `watcher_sites.conf` file is excluded from git to prevent exposing sensitive URLs
- **Log Files**: Ensure log directories have appropriate permissions
- **Cron Jobs**: Run with appropriate user permissions (avoid root unless necessary)
- **File Access**: The system requires read access to log files and web application directories

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is open source. Please check the repository for license details.

## Support

For issues, feature requests, or questions:
- Create an issue on GitHub
- Review existing documentation
- Check troubleshooting section

---

**Note**: This system is designed for RunCloud environments but can be adapted for other hosting setups by modifying the default paths and log formats.

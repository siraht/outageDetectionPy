# Outage Detection System - LiteSpeed Edition

A comprehensive multi-site outage detection and snapshot system for web applications running on LiteSpeed web server. This system monitors multiple websites and automatically collects detailed diagnostic information when outages are detected and resolved.

## Features

- **Multi-site monitoring**: Monitor multiple websites from a single configuration file
- **Automated outage detection**: Continuously monitors HTTP status codes
- **Enhanced snapshot collection**: Automatically captures system state during outages including:
  - System performance data (CPU, memory, load average) using `sar`
  - Application logs (LiteSpeed access/error, PHP-FPM slow logs)
  - Configuration files (LiteSpeed virtual host and main configs, PHP-FPM configs, LSPHP configs)
  - **File modification tracking**: Identifies and copies all files modified during outage windows
- **Structured reporting**: Generates timestamped reports with JSON summaries
- **Logging**: Per-site logging with timestamps for audit trails
- **LiteSpeed optimized**: Designed specifically for LiteSpeed web server environments

## Requirements

- Linux system (tested on Ubuntu)
- LiteSpeed Web Server
- Python 3.6+
- `curl` for HTTP monitoring
- `sysstat` package for system performance data
- `find` command for file modification tracking
- Root or lsadm access for LiteSpeed configuration file access (optional but recommended)

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
ecommerce-store 8.3 /home/runcloud/webapps/ecommerce-store https://store.my-website.com
```

**Parameters**:
- `AppName`: Unique identifier for the application (used in logs and reports)
- `PHPVersion`: PHP version used by the application (for finding PHP-FPM and LSPHP logs/configs)
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

/usr/local/lsws/
├── conf/
│   ├── httpd_config.conf          # Main LiteSpeed config
│   └── vhosts/                    # Virtual host configurations
│       ├── my-website.conf
│       └── api-service.conf
└── logs/                          # LiteSpeed server logs
    ├── my-website.access.log
    └── my-website.error.log
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

# Or run every 5 minutes (recommended)
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
- **LiteSpeed Access Logs**: HTTP requests during outage period (from both RunCloud and LiteSpeed log locations)
- **LiteSpeed Error Logs**: Server errors and warnings
- **PHP-FPM Slow Logs**: Slow PHP processes (if enabled)

#### Configuration Files
- **LiteSpeed Virtual Host Configuration**: Site-specific LiteSpeed virtual host config
- **LiteSpeed Main Configuration**: Main LiteSpeed server configuration (if accessible)
- **PHP-FPM Configuration**: Application pool configuration
- **LSPHP Configuration**: LiteSpeed PHP configuration files

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
    ├── litespeed_access.slice.log      # LiteSpeed access logs (RunCloud location)
    ├── litespeed_error.slice.log       # LiteSpeed error logs (RunCloud location)
    ├── litespeed_access_alt.slice.log  # LiteSpeed access logs (LiteSpeed location)
    ├── litespeed_error_alt.slice.log   # LiteSpeed error logs (LiteSpeed location)
    ├── php_fpm_slow.slice.log          # PHP-FPM slow logs
    ├── sar_cpu_usage.txt               # CPU performance data
    ├── sar_memory_usage.txt            # Memory performance data
    ├── sar_load_average.txt            # Load average data
    ├── my-website.conf                 # LiteSpeed VHost config (if accessible)
    ├── litespeed_main_config.conf      # LiteSpeed main config (if accessible)
    ├── my-website.conf                 # PHP-FPM config (if found)
    ├── lsphp8.1_config.ini             # LSPHP config (if found)
    ├── modified_files_manifest.txt     # List of modified files
    └── modified_files/                 # Directory containing modified files
        └── [preserved directory structure]
```

## LiteSpeed-Specific Features

### Configuration File Access
- **Virtual Host Configs**: Located in `/usr/local/lsws/conf/vhosts/`
- **Main Config**: Located at `/usr/local/lsws/conf/httpd_config.conf`
- **Access Permissions**: May require root or lsadm group membership

### Log File Locations
The system checks multiple log locations:
- **RunCloud managed logs**: `/home/runcloud/logs/`
- **LiteSpeed native logs**: `/usr/local/lsws/logs/`
- **PHP-FPM logs**: `/var/log/php/`

### LSPHP Configuration
- **Location**: `/usr/local/lsws/lsphpXX/etc/php/X.X/litespeed/php.ini`
- **Version specific**: Automatically matches your specified PHP version
- **LiteSpeed optimized**: Includes LiteSpeed-specific PHP settings

## Customization

### Paths and Directories

You can customize default paths by editing the Python script constants:

```python
DEFAULT_OUTPUT_DIR = Path("/home/runcloud/outage_reports")
DEFAULT_LOG_DIR = Path("/home/runcloud/logs")
DEFAULT_LITESPEED_CONF_DIR = Path("/usr/local/lsws/conf/vhosts")
DEFAULT_LITESPEED_LOG_DIR = Path("/usr/local/lsws/logs")
DEFAULT_PHP_CONF_BASE = Path("/etc/php-rc")
DEFAULT_LSPHP_BASE = Path("/usr/local/lsws")
```

### Log Formats

The system supports multiple LiteSpeed log formats. To modify or add formats, edit the log parsing configuration in `outage_snapshot.py`:

```python
logs_to_collect = {
    "litespeed_access": {
        "path": args.log_dir / f"{args.app_name}_access.log",
        "regex": r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) - - \[([^\]]+)\]',
        "format": '%d/%b/%Y:%H:%M:%S %z'
    },
    # Add more log types as needed
}
```

### Monitoring Frequency

Adjust the cron schedule based on your needs:
- **High frequency**: `* * * * *` (every minute)
- **Standard**: `*/5 * * * *` (every 5 minutes) - **Recommended**
- **Low frequency**: `*/15 * * * *` (every 15 minutes)

## Troubleshooting

### Common Issues

1. **Permission Denied for LiteSpeed Configs**:
   ```bash
   # Add user to lsadm group
   sudo usermod -a -G lsadm $(whoami)
   
   # Or run with sudo (not recommended for production)
   sudo ./outage_snapshot.py [arguments]
   ```

2. **Missing Directories**:
   ```bash
   sudo mkdir -p /home/runcloud/logs /home/runcloud/outage_reports
   sudo chown -R runcloud:runcloud /home/runcloud/
   ```

3. **No System Data**:
   - Ensure `sysstat` is installed: `sudo apt install sysstat`
   - Enable data collection: `sudo systemctl enable sysstat`

4. **LiteSpeed Log File Locations**:
   - Check your LiteSpeed virtual host configuration for custom log paths
   - Verify log directory permissions: `ls -la /usr/local/lsws/logs/`

5. **Python Dependencies**:
   - Ensure Python 3.6+ is installed
   - Check if required modules are available

### LiteSpeed-Specific Debugging

1. **Check LiteSpeed Status**:
   ```bash
   sudo /usr/local/lsws/bin/lswsctrl status
   ```

2. **Verify Virtual Host Configuration**:
   ```bash
   sudo ls -la /usr/local/lsws/conf/vhosts/
   ```

3. **Check LiteSpeed Logs**:
   ```bash
   sudo tail -f /usr/local/lsws/logs/error.log
   sudo tail -f /usr/local/lsws/logs/access.log
   ```

4. **Test Configuration File Access**:
   ```bash
   sudo -u lsadm cat /usr/local/lsws/conf/httpd_config.conf | head
   ```

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
- **LiteSpeed Config Access**: Requires appropriate permissions for LiteSpeed configuration files
- **Log Files**: Ensure log directories have appropriate permissions
- **Cron Jobs**: Run with appropriate user permissions (consider lsadm group membership)
- **File Access**: The system requires read access to log files and web application directories

## Performance Considerations

- **LiteSpeed Integration**: Optimized for LiteSpeed's log formats and directory structure
- **Multiple Log Sources**: Checks both RunCloud and native LiteSpeed log locations
- **Efficient File Operations**: Uses relative paths and efficient file copying
- **Concurrent Site Monitoring**: Processes multiple sites in sequence to avoid overwhelming the server

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly with LiteSpeed environment
5. Submit a pull request

## License

This project is open source. Please check the repository for license details.

## Support

For issues, feature requests, or questions:
- Create an issue on GitHub
- Review existing documentation
- Check troubleshooting section

---

**Note**: This system is specifically designed for LiteSpeed web server environments, particularly those managed by RunCloud. It can be adapted for other LiteSpeed setups by modifying the default paths and log formats in the configuration constants.

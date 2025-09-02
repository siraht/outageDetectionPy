#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Outage Snapshot Collector (Multi-Site Enhanced) - LiteSpeed Edition

A Python script to collect system logs, performance data, configuration files,
and any source files modified during an outage window.
Designed for LiteSpeed web server environments.
"""

import argparse
import subprocess
import shutil
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict

# --- Configuration ---
DEFAULT_OUTPUT_DIR = Path("/home/runcloud/outage_reports")
DEFAULT_LOG_DIR = Path("/home/runcloud/logs")
DEFAULT_LITESPEED_CONF_DIR = Path("/usr/local/lsws/conf/vhosts")
DEFAULT_LITESPEED_LOG_DIR = Path("/usr/local/lsws/logs")
DEFAULT_PHP_CONF_BASE = Path("/etc/php-rc")  # RunCloud PHP configs
DEFAULT_LSPHP_BASE = Path("/usr/local/lsws")  # LiteSpeed PHP configs


def setup_arg_parser() -> argparse.ArgumentParser:
    """Sets up the command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="Collect snapshot data for a web application outage (LiteSpeed Edition).",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--app-name", type=str, required=True, help="The RunCloud application name.")
    parser.add_argument("--start", type=str, required=True, help="Outage start time 'YYYY-MM-DD HH:MM:SS'.")
    parser.add_argument("--end", type=str, required=True, help="Outage end time 'YYYY-MM-DD HH:MM:SS'.")
    parser.add_argument("--php-version", type=str, default="8.2", help="The PHP version of the application.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Base directory for reports.")
    parser.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR, help="Base directory for app logs.")
    parser.add_argument(
        "--app-path",
        type=Path,
        required=True,
        help="The absolute path to the web application's root directory (e.g., /home/runcloud/webapps/my-app)."
    )
    return parser


def run_command(command: list):
    """Executes a shell command and returns its success status, stdout, and stderr."""
    try:
        process = subprocess.run(
            command, capture_output=True, text=True, check=False
        )
        return process.returncode == 0, process.stdout, process.stderr
    except FileNotFoundError:
        return False, "", f"Error: Command '{command[0]}' not found."
    except Exception as e:
        return False, "", f"An unexpected error occurred: {e}"


def create_output_directory(base_dir: Path, app_name: str, start_dt: datetime) -> Path:
    """Creates a unique, timestamped directory for the report."""
    timestamp = start_dt.strftime('%Y%m%d_%H%M%S')
    output_dir = base_dir / f"{app_name}_{timestamp}"
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"✅ Created report directory: {output_dir}")
        return output_dir
    except OSError as e:
        print(f"❌ Critical Error: Could not create output directory: {e}")
        exit(1)


def parse_log_slice(
    log_path: Path, start_dt: datetime, end_dt: datetime,
    date_regex: str, date_format: str
) -> Optional[str]:
    """Extracts lines from a log file that fall within a given time window."""
    if not log_path.is_file():
        print(f"   - ⚠️  Log file not found: {log_path}")
        return None
    relevant_lines = []
    pattern = re.compile(date_regex)
    try:
        with log_path.open('r', errors='ignore') as f:
            for line in f:
                match = pattern.search(line)
                if not match: continue
                try:
                    log_dt = datetime.strptime(match.group(1), date_format)
                    if start_dt <= log_dt <= end_dt:
                        relevant_lines.append(line)
                except ValueError:
                    continue
    except Exception as e:
        print(f"   - ❌ Error reading {log_path}: {e}")
        return None
    return "".join(relevant_lines) if relevant_lines else None


def collect_modified_files(
    output_dir: Path, app_path: Path, start_dt: datetime, end_dt: datetime
) -> dict:
    """Finds and copies all files within the app path modified during the outage."""
    print("\n[+] Searching for files modified during the outage...")
    results = {"copied_files": [], "manifest_path": ""}
    
    if not app_path.is_dir():
        print(f"   - ❌ Error: Application path does not exist: {app_path}")
        results["error"] = "Application path not found."
        return results

    # Format dates for the `find` command
    start_str = start_dt.strftime('%Y-%m-%d %H:%M:%S')
    end_str = end_dt.strftime('%Y-%m-%d %H:%M:%S')
    
    cmd = [
        "find", str(app_path),
        "-type", "f",
        "-newermt", start_str,
        "-not", "-newermt", end_str
    ]
    
    success, stdout, stderr = run_command(cmd)
    
    if not success:
        print(f"   - ❌ Error running find command: {stderr}")
        results["error"] = stderr
        return results

    modified_files = stdout.strip().split('\n')
    if not modified_files or not modified_files[0]:
        print("   - ✅ No files were modified during the outage window.")
        return results

    print(f"   - Found {len(modified_files)} modified file(s). Copying...")
    
    dest_dir = output_dir / "modified_files"
    dest_dir.mkdir()
    
    manifest_path = output_dir / "modified_files_manifest.txt"
    with manifest_path.open('w') as f:
        f.write(f"# Files modified between {start_str} and {end_str}\n\n")
        for file_str in modified_files:
            if not file_str: continue
            
            source_file = Path(file_str)
            relative_path = source_file.relative_to(app_path)
            dest_file_path = dest_dir / relative_path
            dest_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            try:
                shutil.copy2(source_file, dest_file_path)
                f.write(f"{file_str}\n")
                results["copied_files"].append(str(dest_file_path))
            except Exception as e:
                error_msg = f"   - ⚠️  Could not copy {source_file}: {e}"
                print(error_msg)
                f.write(f"# FAILED TO COPY: {file_str} - REASON: {e}\n")
    
    results["manifest_path"] = str(manifest_path)
    print(f"   - ✅ Copied modified files and created manifest.")
    return results


def collect_sar_data(output_dir: Path, start_dt: datetime, end_dt: datetime) -> dict:
    print("\n[+] Collecting historical system performance data with `sar`...")
    results = {}
    start_time_str = start_dt.strftime('%H:%M:%S')
    end_time_str = end_dt.strftime('%H:%M:%S')
    sar_commands = { 
        "cpu_usage": ["sar", "-u", "-s", start_time_str, "-e", end_time_str], 
        "memory_usage": ["sar", "-r", "-s", start_time_str, "-e", end_time_str], 
        "load_average": ["sar", "-q", "-s", start_time_str, "-e", end_time_str] 
    }
    for key, cmd in sar_commands.items():
        success, stdout, stderr = run_command(cmd)
        if not success or "Cannot open" in stderr:
            print(f"   - ⚠️  Could not collect {key}. Is `sysstat` installed?")
            results[key] = f"Error: {stderr}"
        else:
            output_file = output_dir / f"sar_{key}.txt"
            output_file.write_text(stdout)
            results[key] = str(output_file)
            print(f"   - ✅ Saved {key} data to {output_file.name}")
    return results


def get_log_paths_from_handler_conf(app_name: str) -> Dict[str, Path]:
    """Parses the LiteSpeed handler.conf to find log paths."""
    handler_conf_path = Path(f"/etc/lsws-rc/conf.d/{app_name}.d/handler.conf")
    log_paths = {}

    if not handler_conf_path.is_file():
        print(f"   - ℹ️  Handler config not found at {handler_conf_path}, using default log paths.")
        return log_paths

    print(f"   - ℹ️  Parsing {handler_conf_path} for log locations...")
    try:
        content = handler_conf_path.read_text()
        errorlog_match = re.search(r"^\s*errorlog\s+([^\s{]+)", content, re.MULTILINE)
        accesslog_match = re.search(r"^\s*accesslog\s+([^\s{]+)", content, re.MULTILINE)

        if errorlog_match:
            log_paths["litespeed_error"] = Path(errorlog_match.group(1))
            print(f"     - Found error log: {log_paths['litespeed_error']}")
        if accesslog_match:
            log_paths["litespeed_access"] = Path(accesslog_match.group(1))
            print(f"     - Found access log: {log_paths['litespeed_access']}")

    except Exception as e:
        print(f"   - ⚠️  Could not read or parse handler.conf: {e}")

    return log_paths


def collect_config_files(output_dir: Path, app_name: str, php_version: str) -> dict:
    print("\n[+] Collecting LiteSpeed and PHP configuration files...")
    results = {}
    
    # LiteSpeed Virtual Host Configuration
    vhost_conf_path = DEFAULT_LITESPEED_CONF_DIR / f"{app_name}.conf"
    if vhost_conf_path.is_file():
        try:
            shutil.copy(vhost_conf_path, output_dir)
            results["litespeed_vhost_config"] = str(output_dir / vhost_conf_path.name)
            print(f"   - ✅ Copied LiteSpeed VHost config: {vhost_conf_path.name}")
        except PermissionError:
            results["litespeed_vhost_config"] = "Access denied (requires root/lsadm permissions)"
            print(f"   - ⚠️  Cannot access LiteSpeed VHost config: Permission denied")
    else:
        results["litespeed_vhost_config"] = "Not found"
        print(f"   - ⚠️  LiteSpeed VHost config not found: {vhost_conf_path}")

    # Main LiteSpeed Configuration (if accessible)
    main_conf_path = Path("/usr/local/lsws/conf/httpd_config.conf")
    if main_conf_path.is_file():
        try:
            shutil.copy(main_conf_path, output_dir / "litespeed_main_config.conf")
            results["litespeed_main_config"] = str(output_dir / "litespeed_main_config.conf")
            print(f"   - ✅ Copied LiteSpeed main config")
        except PermissionError:
            results["litespeed_main_config"] = "Access denied (requires root/lsadm permissions)"
            print(f"   - ⚠️  Cannot access LiteSpeed main config: Permission denied")
    else:
        results["litespeed_main_config"] = "Not found"

    # PHP-FPM Configuration (RunCloud style)
    php_conf_path = DEFAULT_PHP_CONF_BASE / php_version / "fpm/pool.d" / f"{app_name}.conf"
    if php_conf_path.is_file():
        shutil.copy(php_conf_path, output_dir)
        results["php_fpm_config"] = str(output_dir / php_conf_path.name)
        print(f"   - ✅ Copied PHP-FPM config: {php_conf_path.name}")
    else:
        results["php_fpm_config"] = "Not found"
        print(f"   - ⚠️  PHP-FPM config not found: {php_conf_path}")

    # LiteSpeed PHP Configuration
    lsphp_conf_path = DEFAULT_LSPHP_BASE / f"lsphp{php_version.replace('.', '')}" / "etc" / "php" / php_version / "litespeed" / "php.ini"
    if lsphp_conf_path.is_file():
        try:
            shutil.copy(lsphp_conf_path, output_dir / f"lsphp{php_version}_config.ini")
            results["lsphp_config"] = str(output_dir / f"lsphp{php_version}_config.ini")
            print(f"   - ✅ Copied LSPHP config: lsphp{php_version}_config.ini")
        except Exception as e:
            results["lsphp_config"] = f"Error copying: {e}"
            print(f"   - ⚠️  Error copying LSPHP config: {e}")
    else:
        results["lsphp_config"] = "Not found"
        print(f"   - ⚠️  LSPHP config not found: {lsphp_conf_path}")

    return results


def main():
    """Main execution function."""
    parser = setup_arg_parser()
    args = parser.parse_args()

    try:
        start_dt = datetime.strptime(args.start, '%Y-%m-%d %H:%M:%S')
        end_dt = datetime.strptime(args.end, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        print("❌ Critical Error: Invalid date format. Use 'YYYY-MM-DD HH:MM:SS'.")
        exit(1)

    report_dir = create_output_directory(args.output_dir, args.app_name, start_dt)
    collection_results = {"report_directory": str(report_dir)}

    print("\n[+] Collecting application log slices...")
    # Get log paths from handler.conf if available
    handler_log_paths = get_log_paths_from_handler_conf(args.app_name)

    logs_to_collect = {
        "litespeed_access": {
            "path": handler_log_paths.get("litespeed_access", args.log_dir / f"{args.app_name}_access.log"),
            "regex": r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) - - \[([^\]]+)\]',
            "format": '%d/%b/%Y:%H:%M:%S %z'
        },
        "litespeed_error": {
            "path": handler_log_paths.get("litespeed_error", args.log_dir / f"{args.app_name}_error.log"),
            "regex": r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',
            "format": '%Y-%m-%d %H:%M:%S'
        },
        "litespeed_access_alt": {
            "path": DEFAULT_LITESPEED_LOG_DIR / f"{args.app_name}.access.log",
            "regex": r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) - - \[([^\]]+)\]',
            "format": '%d/%b/%Y:%H:%M:%S %z'
        },
        "litespeed_error_alt": {
            "path": DEFAULT_LITESPEED_LOG_DIR / f"{args.app_name}.error.log",
            "regex": r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',
            "format": '%Y-%m-%d %H:%M:%S'
        },
        "php_fpm_slow": {
            "path": Path(f"/var/log/php/php{args.php_version}-fpm-slow.log"),
            "regex": r'^(\[\d{2}-[A-Za-z]{3}-\d{4} \d{2}:\d{2}:\d{2}\])',
            "format": '%d-%b-%Y %H:%M:%S'
        }
    }

    collection_results["logs"] = {}
    for name, config in logs_to_collect.items():
        content = parse_log_slice(config["path"], start_dt, end_dt, config["regex"], config["format"])
        if content:
            output_file = report_dir / f"{name}.slice.log"
            output_file.write_text(content)
            collection_results["logs"][name] = str(output_file)
            print(f"   - ✅ Saved log slice: {output_file.name}")
        else:
            collection_results["logs"][name] = "No relevant entries or file missing."

    # Collect all data
    collection_results["modified_files_data"] = collect_modified_files(report_dir, args.app_path, start_dt, end_dt)
    collection_results["sar_data"] = collect_sar_data(report_dir, start_dt, end_dt)
    collection_results["configs"] = collect_config_files(report_dir, args.app_name, args.php_version)
    
    summary_file = report_dir / "summary.json"
    with summary_file.open('w') as f:
        json.dump(collection_results, f, indent=4)
        
    print(f"\n✨ Snapshot complete! All data saved in:\n{report_dir}")


if __name__ == "__main__":
    main()

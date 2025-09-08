"""
Error reporting and logging system for comprehensive error tracking.

This module provides error reporting functionality including file logging,
error statistics, and error report generation.
"""

import logging
import json
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import threading
import os

from px_ui.error_handling.error_manager import ErrorInfo, ErrorSeverity, ErrorCategory, get_error_manager


class ErrorReporter:
    """
    Comprehensive error reporting and logging system.
    
    Provides functionality for:
    - File-based error logging
    - Error statistics tracking
    - Error report generation
    - Error trend analysis
    """
    
    def __init__(self, log_directory: Optional[Path] = None):
        """
        Initialize error reporter.
        
        Args:
            log_directory: Directory for error log files
        """
        self.logger = logging.getLogger(__name__)
        
        # Set up log directory
        if log_directory is None:
            log_directory = Path.cwd() / "logs" / "errors"
        
        self.log_directory = Path(log_directory)
        self.log_directory.mkdir(parents=True, exist_ok=True)
        
        # Log files
        self.error_log_file = self.log_directory / "error_log.jsonl"
        self.stats_file = self.log_directory / "error_stats.json"
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Statistics tracking
        self._stats = {
            'total_errors': 0,
            'errors_by_severity': {severity.value: 0 for severity in ErrorSeverity},
            'errors_by_category': {category.value: 0 for category in ErrorCategory},
            'errors_by_hour': {},
            'errors_by_day': {},
            'most_common_errors': {},
            'error_trends': []
        }
        
        # Load existing stats
        self._load_stats()
        
        # Set up error manager callback
        error_manager = get_error_manager()
        error_manager.add_error_callback(self._on_error_occurred)
        
        self.logger.info(f"Error reporter initialized with log directory: {self.log_directory}")
    
    def _on_error_occurred(self, error_info: ErrorInfo):
        """Handle error occurrence callback from error manager."""
        try:
            self._log_error_to_file(error_info)
            self._update_statistics(error_info)
            self._save_stats()
        except Exception as e:
            # Avoid recursive error reporting
            self.logger.error(f"Failed to report error: {e}")
    
    def _log_error_to_file(self, error_info: ErrorInfo):
        """Log error to JSON Lines file."""
        with self._lock:
            try:
                # Create error record
                error_record = {
                    'timestamp': error_info.timestamp.isoformat(),
                    'error_id': error_info.error_id,
                    'category': error_info.category.value,
                    'severity': error_info.severity.value,
                    'message': error_info.message,
                    'details': error_info.details,
                    'context': error_info.context,
                    'exception_type': type(error_info.exception).__name__ if error_info.exception else None,
                    'exception_message': str(error_info.exception) if error_info.exception else None,
                    'recovery_attempted': error_info.recovery_attempted,
                    'recovery_successful': error_info.recovery_successful,
                    'retry_count': error_info.retry_count
                }
                
                # Append to log file
                with open(self.error_log_file, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(error_record, ensure_ascii=False) + '\n')
                
            except Exception as e:
                self.logger.error(f"Failed to log error to file: {e}")
    
    def _update_statistics(self, error_info: ErrorInfo):
        """Update error statistics."""
        with self._lock:
            # Total errors
            self._stats['total_errors'] += 1
            
            # By severity
            self._stats['errors_by_severity'][error_info.severity.value] += 1
            
            # By category
            self._stats['errors_by_category'][error_info.category.value] += 1
            
            # By hour
            hour_key = error_info.timestamp.strftime('%Y-%m-%d %H:00')
            if hour_key not in self._stats['errors_by_hour']:
                self._stats['errors_by_hour'][hour_key] = 0
            self._stats['errors_by_hour'][hour_key] += 1
            
            # By day
            day_key = error_info.timestamp.strftime('%Y-%m-%d')
            if day_key not in self._stats['errors_by_day']:
                self._stats['errors_by_day'][day_key] = 0
            self._stats['errors_by_day'][day_key] += 1
            
            # Most common errors
            error_key = f"{error_info.category.value}:{error_info.message}"
            if error_key not in self._stats['most_common_errors']:
                self._stats['most_common_errors'][error_key] = 0
            self._stats['most_common_errors'][error_key] += 1
            
            # Clean up old hourly data (keep last 7 days)
            cutoff_time = datetime.now() - timedelta(days=7)
            cutoff_hour = cutoff_time.strftime('%Y-%m-%d %H:00')
            
            self._stats['errors_by_hour'] = {
                k: v for k, v in self._stats['errors_by_hour'].items()
                if k >= cutoff_hour
            }
    
    def _load_stats(self):
        """Load existing statistics from file."""
        try:
            if self.stats_file.exists():
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    saved_stats = json.load(f)
                    self._stats.update(saved_stats)
                self.logger.info("Loaded existing error statistics")
        except Exception as e:
            self.logger.warning(f"Failed to load error statistics: {e}")
    
    def _save_stats(self):
        """Save statistics to file."""
        with self._lock:
            try:
                with open(self.stats_file, 'w', encoding='utf-8') as f:
                    json.dump(self._stats, f, indent=2, ensure_ascii=False)
            except Exception as e:
                self.logger.error(f"Failed to save error statistics: {e}")
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """Get current error statistics."""
        with self._lock:
            return self._stats.copy()
    
    def get_recent_errors(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get recent errors from log file."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_errors = []
        
        try:
            if self.error_log_file.exists():
                with open(self.error_log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        try:
                            error_record = json.loads(line.strip())
                            error_time = datetime.fromisoformat(error_record['timestamp'])
                            
                            if error_time >= cutoff_time:
                                recent_errors.append(error_record)
                        except (json.JSONDecodeError, ValueError, KeyError):
                            continue
        
        except Exception as e:
            self.logger.error(f"Failed to read recent errors: {e}")
        
        return sorted(recent_errors, key=lambda x: x['timestamp'], reverse=True)
    
    def generate_error_report(self, output_file: Optional[Path] = None, 
                            format: str = 'html') -> Path:
        """
        Generate comprehensive error report.
        
        Args:
            output_file: Output file path (auto-generated if None)
            format: Report format ('html', 'json', 'csv')
            
        Returns:
            Path to generated report file
        """
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = self.log_directory / f"error_report_{timestamp}.{format}"
        
        if format == 'html':
            return self._generate_html_report(output_file)
        elif format == 'json':
            return self._generate_json_report(output_file)
        elif format == 'csv':
            return self._generate_csv_report(output_file)
        else:
            raise ValueError(f"Unsupported report format: {format}")
    
    def _generate_html_report(self, output_file: Path) -> Path:
        """Generate HTML error report."""
        stats = self.get_error_statistics()
        recent_errors = self.get_recent_errors(hours=168)  # Last week
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>px UI Client - Error Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f8f9fa; padding: 20px; border-radius: 5px; }}
        .section {{ margin: 20px 0; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }}
        .stat-card {{ background-color: #e9ecef; padding: 15px; border-radius: 5px; }}
        .error-table {{ width: 100%; border-collapse: collapse; }}
        .error-table th, .error-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        .error-table th {{ background-color: #f2f2f2; }}
        .severity-critical {{ color: #dc3545; font-weight: bold; }}
        .severity-high {{ color: #fd7e14; font-weight: bold; }}
        .severity-medium {{ color: #ffc107; }}
        .severity-low {{ color: #28a745; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>px UI Client - Error Report</h1>
        <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="section">
        <h2>Error Statistics</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Total Errors</h3>
                <p style="font-size: 24px; font-weight: bold;">{stats['total_errors']}</p>
            </div>
            <div class="stat-card">
                <h3>Critical Errors</h3>
                <p style="font-size: 24px; font-weight: bold; color: #dc3545;">
                    {stats['errors_by_severity'].get('critical', 0)}
                </p>
            </div>
            <div class="stat-card">
                <h3>High Priority</h3>
                <p style="font-size: 24px; font-weight: bold; color: #fd7e14;">
                    {stats['errors_by_severity'].get('high', 0)}
                </p>
            </div>
            <div class="stat-card">
                <h3>Medium Priority</h3>
                <p style="font-size: 24px; font-weight: bold; color: #ffc107;">
                    {stats['errors_by_severity'].get('medium', 0)}
                </p>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>Errors by Category</h2>
        <table class="error-table">
            <tr><th>Category</th><th>Count</th><th>Percentage</th></tr>
"""
        
        total_errors = stats['total_errors']
        for category, count in stats['errors_by_category'].items():
            if count > 0:
                percentage = (count / total_errors * 100) if total_errors > 0 else 0
                html_content += f"""
            <tr>
                <td>{category.replace('_', ' ').title()}</td>
                <td>{count}</td>
                <td>{percentage:.1f}%</td>
            </tr>
"""
        
        html_content += """
        </table>
    </div>
    
    <div class="section">
        <h2>Recent Errors (Last 7 Days)</h2>
        <table class="error-table">
            <tr>
                <th>Timestamp</th>
                <th>Severity</th>
                <th>Category</th>
                <th>Message</th>
                <th>Recovery</th>
            </tr>
"""
        
        for error in recent_errors[:50]:  # Show last 50 errors
            severity_class = f"severity-{error['severity']}"
            recovery_status = "✓" if error.get('recovery_successful') else ("⚠" if error.get('recovery_attempted') else "✗")
            
            html_content += f"""
            <tr>
                <td>{error['timestamp'][:19]}</td>
                <td class="{severity_class}">{error['severity'].upper()}</td>
                <td>{error['category'].replace('_', ' ').title()}</td>
                <td>{error['message'][:100]}{'...' if len(error['message']) > 100 else ''}</td>
                <td>{recovery_status}</td>
            </tr>
"""
        
        html_content += """
        </table>
    </div>
</body>
</html>
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self.logger.info(f"HTML error report generated: {output_file}")
        return output_file
    
    def _generate_json_report(self, output_file: Path) -> Path:
        """Generate JSON error report."""
        report_data = {
            'generated_at': datetime.now().isoformat(),
            'statistics': self.get_error_statistics(),
            'recent_errors': self.get_recent_errors(hours=168)
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"JSON error report generated: {output_file}")
        return output_file
    
    def _generate_csv_report(self, output_file: Path) -> Path:
        """Generate CSV error report."""
        recent_errors = self.get_recent_errors(hours=168)
        
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Write header
            writer.writerow([
                'Timestamp', 'Error ID', 'Category', 'Severity', 'Message', 
                'Details', 'Exception Type', 'Recovery Attempted', 'Recovery Successful'
            ])
            
            # Write error data
            for error in recent_errors:
                writer.writerow([
                    error['timestamp'],
                    error['error_id'],
                    error['category'],
                    error['severity'],
                    error['message'],
                    error.get('details', ''),
                    error.get('exception_type', ''),
                    error.get('recovery_attempted', False),
                    error.get('recovery_successful', False)
                ])
        
        self.logger.info(f"CSV error report generated: {output_file}")
        return output_file
    
    def cleanup_old_logs(self, days_to_keep: int = 30):
        """Clean up old log files."""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        try:
            # Clean up error log file
            if self.error_log_file.exists():
                temp_file = self.error_log_file.with_suffix('.tmp')
                
                with open(self.error_log_file, 'r', encoding='utf-8') as infile, \
                     open(temp_file, 'w', encoding='utf-8') as outfile:
                    
                    for line in infile:
                        try:
                            error_record = json.loads(line.strip())
                            error_time = datetime.fromisoformat(error_record['timestamp'])
                            
                            if error_time >= cutoff_date:
                                outfile.write(line)
                        except (json.JSONDecodeError, ValueError, KeyError):
                            continue
                
                # Replace original file
                temp_file.replace(self.error_log_file)
                
            # Clean up old report files
            for report_file in self.log_directory.glob("error_report_*.html"):
                if report_file.stat().st_mtime < cutoff_date.timestamp():
                    report_file.unlink()
            
            for report_file in self.log_directory.glob("error_report_*.json"):
                if report_file.stat().st_mtime < cutoff_date.timestamp():
                    report_file.unlink()
            
            for report_file in self.log_directory.glob("error_report_*.csv"):
                if report_file.stat().st_mtime < cutoff_date.timestamp():
                    report_file.unlink()
            
            self.logger.info(f"Cleaned up error logs older than {days_to_keep} days")
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old logs: {e}")


# Global error reporter instance
_global_error_reporter: Optional[ErrorReporter] = None


def get_error_reporter() -> ErrorReporter:
    """Get the global error reporter instance."""
    global _global_error_reporter
    if _global_error_reporter is None:
        _global_error_reporter = ErrorReporter()
    return _global_error_reporter


def generate_error_report(output_file: Optional[Path] = None, format: str = 'html') -> Path:
    """Convenience function to generate error report."""
    return get_error_reporter().generate_error_report(output_file, format)
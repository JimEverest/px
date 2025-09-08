"""
Log rotation and automatic cleanup of old monitoring data.

This module provides log rotation capabilities for monitoring data,
including time-based and size-based rotation with configurable retention policies.
"""

import os
import threading
import time
import gzip
import shutil
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
from enum import Enum


class RotationPolicy(Enum):
    """Log rotation policies."""
    TIME_BASED = "time"
    SIZE_BASED = "size"
    COUNT_BASED = "count"


@dataclass
class RotationConfig:
    """Configuration for log rotation."""
    policy: RotationPolicy
    max_size_mb: int = 10  # For size-based rotation
    max_age_hours: int = 24  # For time-based rotation
    max_count: int = 1000  # For count-based rotation
    max_files: int = 5  # Maximum rotated files to keep
    compress_old: bool = True  # Compress rotated files
    cleanup_interval: int = 3600  # Cleanup interval in seconds


@dataclass
class LogStats:
    """Log rotation statistics."""
    total_entries: int
    rotated_files: int
    compressed_files: int
    total_size_mb: float
    oldest_entry: Optional[datetime]
    newest_entry: Optional[datetime]
    last_rotation: Optional[datetime]


class LogRotator:
    """
    Handles log rotation and cleanup of old monitoring data.
    
    Supports multiple rotation policies and automatic cleanup of old data
    with configurable retention policies.
    """
    
    def __init__(self, 
                 log_directory: str = "logs",
                 config: Optional[RotationConfig] = None):
        """
        Initialize log rotator.
        
        Args:
            log_directory: Directory to store log files
            config: Rotation configuration
        """
        self.log_directory = Path(log_directory)
        self.config = config or RotationConfig(RotationPolicy.COUNT_BASED)
        
        # Ensure log directory exists
        self.log_directory.mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self.stats = LogStats(0, 0, 0, 0.0, None, None, None)
        
        # Rotation control
        self._rotation_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        
        # Callbacks for rotation events
        self._rotation_callbacks: List[Callable[[str, int], None]] = []
        self._cleanup_callbacks: List[Callable[[List[str]], None]] = []
        
        # Current log data (in-memory before rotation)
        self._current_entries: List[Dict] = []
        self._current_size = 0
        
    def start_rotation(self):
        """Start background log rotation."""
        if self._rotation_thread and self._rotation_thread.is_alive():
            return
        
        self._stop_event.clear()
        self._rotation_thread = threading.Thread(
            target=self._rotation_loop,
            name="LogRotator",
            daemon=True
        )
        self._rotation_thread.start()
    
    def stop_rotation(self):
        """Stop background log rotation."""
        self._stop_event.set()
        
        if self._rotation_thread and self._rotation_thread.is_alive():
            self._rotation_thread.join(timeout=2.0)
    
    def add_rotation_callback(self, callback: Callable[[str, int], None]):
        """
        Add callback for rotation events.
        
        Args:
            callback: Function called with (filename, entries_count) when rotation occurs
        """
        with self._lock:
            self._rotation_callbacks.append(callback)
    
    def add_cleanup_callback(self, callback: Callable[[List[str]], None]):
        """
        Add callback for cleanup events.
        
        Args:
            callback: Function called with list of cleaned up filenames
        """
        with self._lock:
            self._cleanup_callbacks.append(callback)
    
    def add_entry(self, entry: Dict):
        """
        Add a monitoring entry to current log.
        
        Args:
            entry: Monitoring entry to add
        """
        with self._lock:
            self._current_entries.append(entry)
            self._current_size += len(str(entry))
            self.stats.total_entries += 1
            
            # Update timestamp tracking
            if 'timestamp' in entry:
                timestamp = entry['timestamp']
                if isinstance(timestamp, str):
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                
                if self.stats.oldest_entry is None or timestamp < self.stats.oldest_entry:
                    self.stats.oldest_entry = timestamp
                if self.stats.newest_entry is None or timestamp > self.stats.newest_entry:
                    self.stats.newest_entry = timestamp
        
        # Check if rotation is needed
        if self._should_rotate():
            self._rotate_logs()
    
    def force_rotation(self) -> str:
        """
        Force immediate log rotation.
        
        Returns:
            Path to rotated log file
        """
        return self._rotate_logs()
    
    def cleanup_old_logs(self) -> List[str]:
        """
        Clean up old log files based on retention policy.
        
        Returns:
            List of cleaned up file paths
        """
        cleaned_files = []
        
        try:
            # Get all log files sorted by modification time
            log_files = []
            for file_path in self.log_directory.glob("monitoring_*.log*"):
                if file_path.is_file():
                    log_files.append((file_path, file_path.stat().st_mtime))
            
            # Sort by modification time (oldest first)
            log_files.sort(key=lambda x: x[1])
            
            # Remove files exceeding max_files limit
            if len(log_files) > self.config.max_files:
                files_to_remove = log_files[:-self.config.max_files]
                for file_path, _ in files_to_remove:
                    try:
                        file_path.unlink()
                        cleaned_files.append(str(file_path))
                    except Exception as e:
                        print(f"Error removing log file {file_path}: {e}")
            
            # Remove files older than max_age
            if self.config.max_age_hours > 0:
                cutoff_time = time.time() - (self.config.max_age_hours * 3600)
                for file_path, mtime in log_files:
                    if mtime < cutoff_time and file_path.exists():
                        try:
                            file_path.unlink()
                            if str(file_path) not in cleaned_files:
                                cleaned_files.append(str(file_path))
                        except Exception as e:
                            print(f"Error removing old log file {file_path}: {e}")
            
            # Notify callbacks
            if cleaned_files:
                with self._lock:
                    for callback in self._cleanup_callbacks:
                        try:
                            callback(cleaned_files)
                        except Exception as e:
                            print(f"Error in cleanup callback: {e}")
            
        except Exception as e:
            print(f"Error during log cleanup: {e}")
        
        return cleaned_files
    
    def get_log_files(self) -> List[Dict]:
        """
        Get information about all log files.
        
        Returns:
            List of dictionaries with file information
        """
        files_info = []
        
        try:
            for file_path in self.log_directory.glob("monitoring_*.log*"):
                if file_path.is_file():
                    stat = file_path.stat()
                    files_info.append({
                        'path': str(file_path),
                        'name': file_path.name,
                        'size_mb': stat.st_size / (1024 * 1024),
                        'modified': datetime.fromtimestamp(stat.st_mtime),
                        'compressed': file_path.suffix == '.gz'
                    })
            
            # Sort by modification time (newest first)
            files_info.sort(key=lambda x: x['modified'], reverse=True)
            
        except Exception as e:
            print(f"Error getting log files info: {e}")
        
        return files_info
    
    def get_stats(self) -> LogStats:
        """Get current log rotation statistics."""
        with self._lock:
            # Update file counts
            log_files = self.get_log_files()
            self.stats.rotated_files = len([f for f in log_files if not f['compressed']])
            self.stats.compressed_files = len([f for f in log_files if f['compressed']])
            self.stats.total_size_mb = sum(f['size_mb'] for f in log_files)
            
            return self.stats
    
    def _should_rotate(self) -> bool:
        """Check if log rotation should occur."""
        with self._lock:
            if self.config.policy == RotationPolicy.COUNT_BASED:
                return len(self._current_entries) >= self.config.max_count
            
            elif self.config.policy == RotationPolicy.SIZE_BASED:
                size_mb = self._current_size / (1024 * 1024)
                return size_mb >= self.config.max_size_mb
            
            elif self.config.policy == RotationPolicy.TIME_BASED:
                if not self._current_entries:
                    return False
                
                oldest_entry = min(
                    entry.get('timestamp', datetime.now())
                    for entry in self._current_entries
                    if 'timestamp' in entry
                )
                
                if isinstance(oldest_entry, str):
                    oldest_entry = datetime.fromisoformat(oldest_entry.replace('Z', '+00:00'))
                
                age = datetime.now() - oldest_entry
                return age.total_seconds() >= (self.config.max_age_hours * 3600)
        
        return False
    
    def _rotate_logs(self) -> str:
        """Perform log rotation."""
        with self._lock:
            if not self._current_entries:
                return ""
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"monitoring_{timestamp}.log"
            file_path = self.log_directory / filename
            
            try:
                # Write current entries to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    for entry in self._current_entries:
                        f.write(f"{entry}\n")
                
                entries_count = len(self._current_entries)
                
                # Compress if configured
                if self.config.compress_old:
                    compressed_path = file_path.with_suffix('.log.gz')
                    with open(file_path, 'rb') as f_in:
                        with gzip.open(compressed_path, 'wb') as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    
                    # Remove uncompressed file
                    file_path.unlink()
                    file_path = compressed_path
                
                # Clear current entries
                self._current_entries.clear()
                self._current_size = 0
                self.stats.last_rotation = datetime.now()
                
                # Notify callbacks
                for callback in self._rotation_callbacks:
                    try:
                        callback(str(file_path), entries_count)
                    except Exception as e:
                        print(f"Error in rotation callback: {e}")
                
                return str(file_path)
                
            except Exception as e:
                print(f"Error during log rotation: {e}")
                return ""
    
    def _rotation_loop(self):
        """Background rotation and cleanup loop."""
        while not self._stop_event.wait(self.config.cleanup_interval):
            try:
                # Check if rotation is needed
                if self._should_rotate():
                    self._rotate_logs()
                
                # Perform cleanup
                self.cleanup_old_logs()
                
            except Exception as e:
                print(f"Error in rotation loop: {e}")
    
    def export_current_entries(self) -> List[Dict]:
        """
        Export current in-memory entries.
        
        Returns:
            List of current monitoring entries
        """
        with self._lock:
            return self._current_entries.copy()
    
    def clear_current_entries(self):
        """Clear current in-memory entries without rotation."""
        with self._lock:
            self._current_entries.clear()
            self._current_size = 0
    
    def load_log_file(self, file_path: str) -> List[Dict]:
        """
        Load entries from a rotated log file.
        
        Args:
            file_path: Path to log file
            
        Returns:
            List of entries from the file
        """
        entries = []
        path = Path(file_path)
        
        try:
            if path.suffix == '.gz':
                # Compressed file
                with gzip.open(path, 'rt', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                # Assuming entries are stored as string representations
                                entry = eval(line)  # Note: In production, use json.loads or ast.literal_eval
                                entries.append(entry)
                            except Exception as e:
                                print(f"Error parsing log entry: {e}")
            else:
                # Uncompressed file
                with open(path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                entry = eval(line)
                                entries.append(entry)
                            except Exception as e:
                                print(f"Error parsing log entry: {e}")
                                
        except Exception as e:
            print(f"Error loading log file {file_path}: {e}")
        
        return entries
import asyncio
import os
import signal
import sys
import time
import psutil
import subprocess
from datetime import datetime
import logging
from collections import deque
import shutil
from pathlib import Path
from typing import Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('watchdog.log'),
        logging.StreamHandler()
    ]
)

class AsyncErrorDetector:
    ASYNC_RELATED_ERRORS = [
        "asyncio.exceptions",
        "ConnectionResetError",
        "TimeoutError",
        "ClientConnectorError",
        "ServerDisconnectedError",
        "socket.send() raised exception",
        "RuntimeError: Event loop is closed",
        "RuntimeError: Session is closed",
        "aiohttp.client_exceptions",
        "pyrogram.errors.FloodWait",
    ]

    @staticmethod
    def is_async_error(error_text: str) -> bool:
        return any(err in error_text for err in AsyncErrorDetector.ASYNC_RELATED_ERRORS)

class LogMonitor:
    def __init__(self, log_file='logs.txt'):
        self.log_file = log_file
        self.last_position = 0
        self.error_history = deque(maxlen=100)  
        self.critical_errors = [
            "RuntimeError",
            "ConnectionError",
            "ServerDisconnectedError",
            "ClientConnectorError",
            "socket.send() raised exception"
        ]
        self.socket_errors = deque(maxlen=10)  # Track last 10 socket errors
        self.async_detector = AsyncErrorDetector()
        self.last_error: Optional[str] = None
        self.error_count = 0
        self.error_threshold = 3
        self.error_window = 300  # 5 minutes
        
    async def analyze_socket_error(self, error_line):
        """Analyze socket.send() errors for patterns"""
        try:
            timestamp = error_line[:19]
            self.socket_errors.append({
                'timestamp': timestamp,
                'full_error': error_line,
                'count': len(self.socket_errors) + 1
            })
            
            # Check for frequent errors
            if len(self.socket_errors) >= 3:
                time_diffs = []
                for i in range(len(self.socket_errors) - 1):
                    t1 = datetime.strptime(self.socket_errors[i]['timestamp'], '%d-%m-%Y %H:%M:%S')
                    t2 = datetime.strptime(self.socket_errors[i + 1]['timestamp'], '%d-%m-%Y %H:%M:%S')
                    time_diffs.append((t2 - t1).total_seconds())
                
                if any(diff < 60 for diff in time_diffs):
                    logging.warning("Multiple socket.send() errors detected in short period")
                    return "frequent_socket_errors"
            
            return None
        except Exception as e:
            logging.error(f"Error analyzing socket error: {e}")
            return None

    async def check_logs(self) -> Optional[str]:
        try:
            if not os.path.exists(self.log_file):
                return None

            with open(self.log_file, 'r') as f:
                f.seek(self.last_position)
                new_lines = f.readlines()
                self.last_position = f.tell()

                for line in new_lines:
                    if self.async_detector.is_async_error(line):
                        self.error_history.append({
                            'time': time.time(),
                            'error': line.strip()
                        })
                        self.last_error = line.strip()
                        return line.strip()

            # Clean old errors
            current_time = time.time()
            self.error_history = deque(
                [e for e in self.error_history if current_time - e['time'] < self.error_window],
                maxlen=100
            )

            return None
        except Exception as e:
            logging.error(f"Error reading logs: {str(e)}")
            return None

    def should_trigger_restart(self) -> bool:
        """Determine if errors are severe enough to trigger restart"""
        if not self.error_history:
            return False

        current_time = time.time()
        recent_errors = [
            e for e in self.error_history 
            if current_time - e['time'] < self.error_window
        ]

        return len(recent_errors) >= self.error_threshold

class StorageMonitor:
    def __init__(self, base_path):
        self.base_path = Path(base_path)
        self.downloads_path = self.base_path / 'downloads'
        self.cache_path = self.base_path / 'cache'
        self.min_free_space = 1024 * 1024 * 1024  # 1GB minimum free space

    def check_storage(self):
        """Check storage space and clean if necessary"""
        try:
            total, used, free = shutil.disk_usage(self.base_path)
            free_gb = free / (1024 * 1024 * 1024)
            
            if free < self.min_free_space:
                logging.warning(f"Low storage space: {free_gb:.2f}GB free")
                return False
            return True
        except Exception as e:
            logging.error(f"Storage check error: {e}")
            return False

    def clean_directories(self):
        """Clean downloads and cache directories"""
        try:
            cleaned_size = 0
            for directory in [self.downloads_path, self.cache_path]:
                if directory.exists():
                    size = sum(f.stat().st_size for f in directory.glob('**/*') if f.is_file())
                    shutil.rmtree(directory)
                    directory.mkdir(exist_ok=True)
                    cleaned_size += size
            
            if cleaned_size > 0:
                logging.info(f"Cleaned {cleaned_size / (1024*1024):.2f}MB from downloads/cache")
            return True
        except Exception as e:
            logging.error(f"Error cleaning directories: {e}")
            return False

class CPUMonitor:
    def __init__(self):
        self.high_cpu_history = deque(maxlen=60)  # Track 30 minutes of readings
        self.cpu_threshold = 99.0
        self.critical_cpu_threshold = 98.0
        self.high_cpu_duration_threshold = 1800  # 30 minutes
        self.cpu_count = psutil.cpu_count()
        
    def add_cpu_reading(self, process):
        """Add CPU reading with system-wide CPU info"""
        try:
            current_time = time.time()
            
            # Get overall system CPU usage
            system_cpu = psutil.cpu_percent(interval=1, percpu=True)
            process_cpu = process.cpu_percent(interval=None)
            
            # Count high CPU cores
            high_cpu_cores = sum(1 for core in system_cpu if core > self.cpu_threshold)
            
            self.high_cpu_history.append({
                'time': current_time,
                'system_cpu': sum(system_cpu) / len(system_cpu),  # Average CPU
                'process_cpu': process_cpu,
                'high_cpu_cores': high_cpu_cores,
                'total_cores': self.cpu_count
            })
            
            # Log if CPU usage is high
            if high_cpu_cores > (self.cpu_count // 2):
                logging.warning(f"High CPU detected - Process: {process_cpu}%, System average: {sum(system_cpu)/len(system_cpu)}%, Cores above threshold: {high_cpu_cores}/{self.cpu_count}")
            
        except Exception as e:
            logging.error(f"Error monitoring CPU: {str(e)}")

    def should_restart(self) -> bool:
        """Determine if CPU usage warrants a restart"""
        if len(self.high_cpu_history) < 60:  # Need full 30 minutes of history
            return False
            
        current_time = time.time()
        oldest_time = self.high_cpu_history[0]['time']
        
        # Check if we have 30 minutes of history
        if current_time - oldest_time < self.high_cpu_duration_threshold:
            return False
            
        # Count readings where CPU usage is problematic
        critical_readings = 0
        for reading in self.high_cpu_history:
            # Check both system and process CPU
            if (reading['system_cpu'] > self.critical_cpu_threshold and 
                reading['process_cpu'] > self.critical_cpu_threshold and
                reading['high_cpu_cores'] > (self.cpu_count // 2)):
                critical_readings += 1
        
        # Only restart if 90% of readings in the last 30 minutes were critical
        critical_percentage = (critical_readings / len(self.high_cpu_history))
        if critical_percentage > 0.9:
            logging.warning(f"Critical CPU usage detected over 30 minutes: {critical_percentage*100:.1f}% of readings were critical")
            return True
            
        return False

class BotWatchdog:
    def __init__(self):
        self.bot_process = None
        self.restart_count = 0
        self.max_restarts = 5
        self.restart_interval = 60
        self.last_restart = 0
        self.bot_script = "python3 -m TeamXmusic"
        self.working_dir = os.path.dirname(os.path.abspath(__file__))
        self.log_monitor = LogMonitor()
        self.log_check_interval = 30  # Increased from 10 to 30 seconds
        self.storage_monitor = StorageMonitor(self.working_dir)
        self.storage_check_interval = 900  # Increased from 300 to 900 seconds (15 minutes)
        self.cpu_monitor = CPUMonitor()
        self.last_activity_check = time.time()
        self.activity_timeout = 600  # Increased from 300 to 600 seconds (10 minutes)
        self.force_restart_count = 0
        self.max_force_restarts = 3
        self.force_restart_interval = 3600  # 1 hour
        self.retry_delays = [5, 10, 30, 60, 120]  # Progressive retry delays
        self.current_retry = 0
        self.max_startup_attempts = 99
        self.startup_retry_delay = 10
        self.forced_restart_needed = False

    async def retry_with_backoff(self, func, *args, **kwargs):
        """Execute function with retry logic"""
        for attempt, delay in enumerate(self.retry_delays):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == len(self.retry_delays) - 1:
                    raise
                logging.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay}s...")
                await asyncio.sleep(delay)

    async def start_bot(self):
        """Start the bot process with retries"""
        for attempt in range(self.max_startup_attempts):
            try:
                self.force_restart_count = 0
                self.storage_monitor.clean_directories()

                if os.path.exists('logs.txt'):
                    with open('logs.txt', 'w') as f:
                        f.truncate(0)

                self.bot_process = subprocess.Popen(
                    self.bot_script.split(),
                    cwd=self.working_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    preexec_fn=os.setsid
                )
                logging.info(f"Bot process started with PID: {self.bot_process.pid}")
                
                await asyncio.sleep(5)
                if self.bot_process.poll() is None:
                    return True
                
                logging.warning("Bot process terminated immediately")
            except Exception as e:
                logging.error(f"Start attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.max_startup_attempts - 1:
                    await asyncio.sleep(self.startup_retry_delay)
                else:
                    logging.error("Max startup attempts reached")
                    return False
        return False

    def kill_bot(self):
        """Kill the bot process and all its children"""
        if not self.bot_process:
            return
        
        try:
            parent = psutil.Process(self.bot_process.pid)
            for child in parent.children(recursive=True):
                child.terminate()
            parent.terminate()
            logging.info(f"Bot process {self.bot_process.pid} terminated")
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            logging.error(f"Error killing bot process: {str(e)}")
        
        self.bot_process = None

    async def check_bot_activity(self):
        """Check if bot is actually responding and working"""
        try:
            if os.path.exists('logs.txt'):
                last_modified = os.path.getmtime('logs.txt')
                if time.time() - last_modified > self.activity_timeout:
                    logging.warning("Bot appears to be frozen (no log activity)")
                    return False
            return True
        except Exception as e:
            logging.error(f"Activity check error: {e}")
            return False

    async def check_bot_health(self):
        """Enhanced health check focusing on async issues"""
        try:
            return await self.retry_with_backoff(self._check_bot_health_internal)
        except Exception as e:
            if isinstance(e, (asyncio.CancelledError, ConnectionResetError)):
                self.forced_restart_needed = True
            logging.error(f"Health check failed: {str(e)}")
            return False

    async def _check_bot_health_internal(self):
        """Internal health check implementation"""
        if not self.bot_process:
            return False

        process = psutil.Process(self.bot_process.pid)
        if process.status() == psutil.STATUS_ZOMBIE:
            return False

        mem_percent = process.memory_percent()
        if mem_percent > 90:
            logging.warning(f"High memory usage: {mem_percent}%")

        self.cpu_monitor.add_cpu_reading(process)
        
        if self.cpu_monitor.should_restart():
            current_time = time.time()
            if current_time - self.last_restart > self.force_restart_interval:
                if self.force_restart_count < self.max_force_restarts:
                    logging.warning("Forcing restart due to sustained critical CPU usage across multiple cores")
                    self.force_restart_count += 1
                    return False

        if not await self.check_bot_activity():
            return False

        return True

    async def monitor_loop(self):
        """Enhanced monitor loop with error handling"""
        while True:
            try:
                await self.retry_with_backoff(self._monitor_iteration)
            except Exception as e:
                logging.error(f"Monitor loop error: {str(e)}")
                await asyncio.sleep(5)

    async def _monitor_iteration(self):
        """Single iteration of the monitor loop"""
        log_check_counter = 0
        storage_check_counter = 0
        
        while True:
            try:
                if time.time() - self.last_restart > 7200:  # 2 hours
                    self.force_restart_count = 0
                    self.forced_restart_needed = False

                storage_check_counter += 1
                if storage_check_counter >= self.storage_check_interval:
                    storage_check_counter = 0
                    if not self.storage_monitor.check_storage():
                        logging.warning("Low storage space detected, cleaning directories")
                        self.storage_monitor.clean_directories()

                health_check_failed = not await self.check_bot_health()
                if health_check_failed or self.forced_restart_needed:
                    critical_error = await self.log_monitor.check_logs()
                    
                    if (critical_error and self.log_monitor.should_trigger_restart()) or self.forced_restart_needed:
                        current_time = time.time()
                        if current_time - self.last_restart > self.restart_interval:
                            if self.restart_count < self.max_restarts:
                                logging.warning("Restarting due to async-related issues...")
                                self.kill_bot()
                                if await self.start_bot():
                                    self.restart_count += 1
                                    self.last_restart = current_time
                                    self.forced_restart_needed = False
                                    logging.info(f"Bot restarted. Restart count: {self.restart_count}")
                            else:
                                logging.error("Max restart attempts reached.")
                                sys.exit(1)
                else:
                    if time.time() - self.last_restart > 3600:
                        self.restart_count = 0
                        self.forced_restart_needed = False

                await asyncio.sleep(30)  # Increased from 1 to 30 seconds
                
            except Exception as e:
                if isinstance(e, (asyncio.CancelledError, ConnectionResetError)):
                    self.forced_restart_needed = True
                logging.error(f"Monitor loop error: {str(e)}")
                await asyncio.sleep(5)

    def handle_signal(self, signum, frame):
        """Handle termination signals"""
        logging.info(f"Received signal {signum}. Shutting down...")
        self.kill_bot()
        sys.exit(0)

    async def run(self):
        """Start the watchdog"""
        signal.signal(signal.SIGTERM, self.handle_signal)
        signal.signal(signal.SIGINT, self.handle_signal)
        
        logging.info("Starting bot watchdog with log monitoring...")
        await self.start_bot()
        await self.monitor_loop()

if __name__ == "__main__":
    watchdog = BotWatchdog()
    try:
        asyncio.run(watchdog.run())
    except KeyboardInterrupt:
        logging.info("Watchdog stopped by user")
        watchdog.kill_bot()

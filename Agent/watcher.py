import json
import logging
import os
import threading
import time

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from Agent.config import APP_TYPE, BATCH_SIZE, CONFIG_FILE, FLUSH_INTERVAL
from Agent.sender import send_batch

log = logging.getLogger(__name__)


class LogFileHandler(FileSystemEventHandler):
    def __init__(self, app_type: str = APP_TYPE):
        self._app_type = app_type
        self._positions: dict[str, int] = {}
        self._buffer: list[dict] = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._start_flush_timer()

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith(".log"):
            return
        self._tail(event.src_path)

    def _tail(self, path: str):
        pos = self._positions.get(path, 0)
        try:
            # Detect file rotation / truncation
            size = os.path.getsize(path)
            if size < pos:
                log.info("rotation detected for '%s', resetting position", path)
                pos = 0

            with open(path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(pos)
                new_lines = [
                    {
                        "message": line.rstrip(),
                        "app_type": self._app_type,
                        "source": os.path.basename(path),
                    }
                    for line in f
                    if line.strip()
                ]
                self._positions[path] = f.tell()

        except OSError as exc:
            log.error("cannot read '%s': %s", path, exc)
            return

        if not new_lines:
            return

        batch_to_send = None
        with self._lock:
            self._buffer.extend(new_lines)
            if len(self._buffer) >= BATCH_SIZE:
                batch_to_send, self._buffer = self._buffer, []

        if batch_to_send:
            send_batch(batch_to_send)

    def flush(self):
        with self._lock:
            batch, self._buffer = self._buffer, []
        if batch:
            send_batch(batch)

    def stop(self):
        self._stop_event.set()
        self.flush()

    def _start_flush_timer(self):
        def _tick():
            while not self._stop_event.wait(timeout=FLUSH_INTERVAL):
                self.flush()

        threading.Thread(target=_tick, daemon=True, name="flush-timer").start()


class SourceManager:
    def __init__(self, app_type: str = APP_TYPE):
        self._handler = LogFileHandler(app_type=app_type)
        self._observer = Observer()
        self._watches: dict[str, object] = {}  # abs path -> ObservedWatch
        self._lock = threading.Lock()
        self._observer.start()
        self._load_persisted()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _save(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({"sources": list(self._watches.keys())}, f, indent=2)
        except OSError as exc:
            log.error("could not save '%s': %s", CONFIG_FILE, exc)

    def _load_persisted(self):
        if not os.path.isfile(CONFIG_FILE):
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            log.error("could not load '%s': %s", CONFIG_FILE, exc)
            return

        for path in data.get("sources", []):
            result = self._schedule(path)
            log.info("restored %s", result)

    # ------------------------------------------------------------------
    # Internal (caller must hold self._lock, or be in __init__)
    # ------------------------------------------------------------------

    def _schedule(self, path: str) -> str:
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            return f"skipped '{path}' — not a valid directory"
        if path in self._watches:
            return f"already watching '{path}'"
        watch = self._observer.schedule(self._handler, path=path, recursive=True)
        self._watches[path] = watch
        return f"'{path}'"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, path: str) -> str:
        with self._lock:
            msg = self._schedule(path)
            self._save()
        return f"added {msg}"

    def remove(self, path: str) -> str:
        path = os.path.abspath(path)
        with self._lock:
            watch = self._watches.pop(path, None)
            if watch is None:
                return f"not watching '{path}'"
            self._observer.unschedule(watch)
            self._save()
        return f"removed '{path}'"

    def list(self) -> list[str]:
        with self._lock:
            return list(self._watches.keys())

    def stop(self):
        self._handler.stop()
        self._observer.stop()
        self._observer.join()

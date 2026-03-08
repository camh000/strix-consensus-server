# Config Manager - Handles runtime configuration changes

import json
import logging
import os
from typing import Dict, Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)

CONFIG_FILE = "config/runtime_config.json"


class ConfigManager:
    """Manages runtime configuration with hot-reload support"""

    def __init__(self):
        self.config = self._load_default_config()
        self._ensure_config_file()
        self._start_watching()

    def _detect_first_local_model(self) -> str:
        """Scan models directory and return the first available GGUF file"""
        models_dir = os.getenv("MODELS_DIR", "./models")
        try:
            if os.path.exists(models_dir):
                gguf_files = [f for f in os.listdir(models_dir) if f.endswith(".gguf")]
                if gguf_files:
                    # Sort to get consistent ordering
                    gguf_files.sort()
                    first_model = gguf_files[0][:-5]  # Remove .gguf extension
                    logger.info(f"Auto-detected local model: {first_model}")
                    return f"local/{first_model}"
        except Exception as e:
            logger.error(f"Error scanning models directory: {e}")
        return None

    def _load_default_config(self) -> Dict:
        """Load default configuration from environment"""
        worker_count = int(os.getenv("WORKER_COUNT", 3))

        # Try to auto-detect local model first
        local_model = self._detect_first_local_model()

        workers = []
        for i in range(1, 6):  # Max 5 workers
            # Use local model if detected, otherwise fall back to environment
            if local_model:
                model = local_model
            else:
                model = os.getenv(f"WORKER_{i}_MODEL")

            if model:
                workers.append(
                    {
                        "id": f"worker-{i}",
                        "model": model,
                        "port": 8100 + i,
                        "enabled": i <= worker_count,
                    }
                )

        # Use local model for judge if detected
        judge_model = local_model if local_model else os.getenv("JUDGE_MODEL", "")

        return {
            "mode": os.getenv("MODE", "consensus"),
            "single_mode": {"active_worker": "worker-1", "fallback_enabled": True},
            "consensus_mode": {
                "worker_count": worker_count,
                "use_judge": os.getenv("JUDGE_ENABLED", "true").lower() == "true",
                "timeout_seconds": int(os.getenv("CONSENSUS_TIMEOUT", 120)),
                "parallel_dispatch": True,
            },
            "workers": workers,
            "judge": {
                "model": judge_model,
                "port": int(os.getenv("JUDGE_PORT", 8200)),
                "enabled": os.getenv("JUDGE_ENABLED", "true").lower() == "true",
            },
            "performance": {
                "context_size": int(os.getenv("CONTEXT_SIZE", 32768)),
                "batch_size": int(os.getenv("BATCH_SIZE", 512)),
                "n_parallel": int(os.getenv("N_PARALLEL", 4)),
            },
        }

    def _ensure_config_file(self):
        """Ensure config file exists"""
        if not os.path.exists("config"):
            os.makedirs("config")

        if not os.path.exists(CONFIG_FILE):
            self._save_config()
        else:
            # Load existing config
            try:
                with open(CONFIG_FILE, "r") as f:
                    loaded_config = json.load(f)
                    self.config.update(loaded_config)
            except Exception as e:
                logger.error(f"Error loading config: {e}")
                self._save_config()

    def _save_config(self):
        """Save current config to file"""
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)

    def _start_watching(self):
        """Start watching config file for changes"""

        class ConfigHandler(FileSystemEventHandler):
            def __init__(self, manager):
                self.manager = manager

            def on_modified(self, event):
                if event.src_path.endswith("runtime_config.json"):
                    self.manager._reload_config()

        observer = Observer()
        observer.schedule(ConfigHandler(self), path="config", recursive=False)
        observer.start()

    def _reload_config(self):
        """Reload configuration from file"""
        try:
            with open(CONFIG_FILE, "r") as f:
                new_config = json.load(f)
                self.config.update(new_config)
                logger.info("Configuration reloaded")
        except Exception as e:
            logger.error(f"Error reloading config: {e}")

    def get_config(self) -> Dict[str, Any]:
        """Get current configuration"""
        return self.config.copy()

    def get_mode(self) -> str:
        """Get current operating mode"""
        return self.config.get("mode", "consensus")

    def set_mode(
        self,
        mode: str,
        worker_count: int = None,
        active_worker: str = None,
        use_judge: bool = None,
    ):
        """Change operating mode"""
        if mode not in ["single", "consensus"]:
            raise ValueError(f"Invalid mode: {mode}. Must be 'single' or 'consensus'")

        self.config["mode"] = mode

        if mode == "single":
            if active_worker:
                self.config["single_mode"]["active_worker"] = active_worker
        else:
            if worker_count:
                self.config["consensus_mode"]["worker_count"] = min(
                    worker_count, len(self.config["workers"])
                )
            if use_judge is not None:
                self.config["consensus_mode"]["use_judge"] = use_judge

        self._save_config()
        logger.info(f"Mode changed to: {mode}")

    def set_active_worker(self, worker_id: str):
        """Set active worker for single mode"""
        valid_workers = [w["id"] for w in self.config["workers"]]
        if worker_id not in valid_workers:
            raise ValueError(f"Invalid worker: {worker_id}. Valid: {valid_workers}")

        self.config["single_mode"]["active_worker"] = worker_id
        self._save_config()

    def update_consensus_settings(
        self, worker_count: int = None, use_judge: bool = None, timeout: int = None
    ):
        """Update consensus mode settings"""
        if worker_count:
            self.config["consensus_mode"]["worker_count"] = worker_count
        if use_judge is not None:
            self.config["consensus_mode"]["use_judge"] = use_judge
        if timeout:
            self.config["consensus_mode"]["timeout_seconds"] = timeout

        self._save_config()

    def add_worker(self, worker_id: str, model: str, port: int = None):
        """Add a new worker"""
        if not port:
            # Find next available port
            used_ports = [w["port"] for w in self.config["workers"]]
            port = max(used_ports, default=8100) + 1

        self.config["workers"].append(
            {"id": worker_id, "model": model, "port": port, "enabled": True}
        )

        self._save_config()

    def remove_worker(self, worker_id: str):
        """Remove a worker"""
        self.config["workers"] = [
            w for w in self.config["workers"] if w["id"] != worker_id
        ]
        self._save_config()

    def enable_worker(self, worker_id: str):
        """Enable a worker"""
        for worker in self.config["workers"]:
            if worker["id"] == worker_id:
                worker["enabled"] = True
                break
        self._save_config()

    def disable_worker(self, worker_id: str):
        """Disable a worker"""
        for worker in self.config["workers"]:
            if worker["id"] == worker_id:
                worker["enabled"] = False
                break
        self._save_config()

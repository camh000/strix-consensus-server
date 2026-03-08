# Model Pool - Manages worker and judge model instances

import asyncio
import aiohttp
import logging
import os
import subprocess
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class ModelPool:
    """Manages llama-server instances for workers and judge"""

    def __init__(self):
        self.workers = {}
        self.judge = None
        self.processes = {}
        self.base_port = int(os.getenv("WORKER_BASE_PORT", 8101))
        self.judge_port = int(os.getenv("JUDGE_PORT", 8200))
        self.models_dir = os.getenv("MODELS_DIR", "./models")

    async def initialize(self):
        """Initialize model pool from config file"""
        logger.info("Initializing model pool...")

        # Load worker configurations from config file
        import json

        config_file = "config/runtime_config.json"

        try:
            with open(config_file, "r") as f:
                config = json.load(f)

            # Load workers from config
            for worker_config in config.get("workers", []):
                worker_id = worker_config["id"]
                if worker_config.get("enabled", True):
                    self.workers[worker_id] = {
                        "id": worker_id,
                        "model_repo": worker_config["model"],
                        "port": worker_config["port"],
                        "status": "stopped",
                        "process": None,
                        "last_used": None,
                    }
                    logger.info(
                        f"Loaded worker {worker_id} with model {worker_config['model']}"
                    )

            # Load judge from config
            judge_config = config.get("judge", {})
            if judge_config.get("enabled", True) and judge_config.get("model"):
                self.judge = {
                    "id": "judge",
                    "model_repo": judge_config["model"],
                    "port": judge_config.get("port", self.judge_port),
                    "status": "stopped",
                    "process": None,
                }
                logger.info(f"Loaded judge with model {judge_config['model']}")

        except Exception as e:
            logger.error(f"Error loading config file: {e}")
            logger.warning("Falling back to environment variables")

            # Fallback to environment variables
            worker_count = int(os.getenv("WORKER_COUNT", 3))
            for i in range(1, worker_count + 1):
                model_env = os.getenv(f"WORKER_{i}_MODEL")
                if model_env:
                    worker_id = f"worker-{i}"
                    port = self.base_port + i - 1

                    self.workers[worker_id] = {
                        "id": worker_id,
                        "model_repo": model_env,
                        "port": port,
                        "status": "stopped",
                        "process": None,
                        "last_used": None,
                    }

            # Initialize judge from env
            judge_model = os.getenv("JUDGE_MODEL")
            if judge_model:
                self.judge = {
                    "id": "judge",
                    "model_repo": judge_model,
                    "port": self.judge_port,
                    "status": "stopped",
                    "process": None,
                }

        # Start all model servers
        await self.start_all_servers()

    async def start_all_servers(self):
        """Start all llama-server instances"""
        # Start workers
        for worker_id in self.workers:
            await self.start_worker(worker_id)

        # Start judge
        if self.judge:
            await self.start_judge()

    async def start_worker(self, worker_id: str):
        """Start a specific worker"""
        worker = self.workers.get(worker_id)
        if not worker:
            logger.error(f"Worker {worker_id} not found")
            return

        if worker["status"] == "running":
            logger.info(f"Worker {worker_id} already running")
            return

        logger.info(f"Starting worker {worker_id} on port {worker['port']}...")

        try:
            # Download model if needed
            model_path = await self._ensure_model(worker["model_repo"])

            # Start llama-server
            process = self._start_llama_server(
                model_path=model_path, port=worker["port"], name=worker_id
            )

            worker["process"] = process
            worker["status"] = "starting"

            # Wait for server to be ready
            await self._wait_for_server(worker["port"])
            worker["status"] = "running"

            logger.info(f"Worker {worker_id} started successfully")
        except Exception as e:
            worker["status"] = "error"
            logger.error(f"Worker {worker_id} failed to start: {e}")

    async def start_judge(self):
        """Start judge model server"""
        if not self.judge:
            return

        logger.info(f"Starting judge on port {self.judge['port']}...")

        try:
            model_path = await self._ensure_model(self.judge["model_repo"])

            process = self._start_llama_server(
                model_path=model_path, port=self.judge["port"], name="judge"
            )

            self.judge["process"] = process
            self.judge["status"] = "starting"

            await self._wait_for_server(self.judge["port"])
            self.judge["status"] = "running"

            logger.info("Judge started successfully")
        except Exception as e:
            self.judge["status"] = "error"
            logger.error(f"Judge failed to start: {e}")

    def _start_llama_server(
        self, model_path: str, port: int, name: str
    ) -> subprocess.Popen:
        """Start llama-server process"""

        # Build command based on GPU backend
        gpu_backend = os.getenv("GPU_BACKEND", "hip")
        n_gpu_layers = os.getenv("N_GPU_LAYERS", "-1")
        context_size = os.getenv("CONTEXT_SIZE", "32768")

        cmd = [
            "llama-server",
            "-m",
            model_path,
            "--host",
            "0.0.0.0",
            "--port",
            str(port),
            "-c",
            context_size,
            "-ngl",
            n_gpu_layers,
            "-np",
            "4",  # Parallel sequences
        ]

        # GPU-specific flags (hip uses the same -ngl flag already set above)

        # Add flash attention if enabled
        if os.getenv("FLASH_ATTENTION", "true").lower() == "true":
            cmd.append("-fa")

        # Add memory mapping
        if os.getenv("MMAP", "true").lower() == "true":
            cmd.append("--mmap")

        logger.info(f"Starting llama-server: {' '.join(cmd)}")

        # Start process
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        return process

    async def _ensure_model(self, model_path_or_repo: str) -> str:
        """Ensure model exists - handles both local paths and HuggingFace repos"""

        # Check if it's a local model path (starts with local/)
        if model_path_or_repo.startswith("local/"):
            model_name = model_path_or_repo[6:]  # Remove "local/" prefix
            model_path = os.path.join(self.models_dir, f"{model_name}.gguf")

            if os.path.exists(model_path):
                logger.info(f"Using local model: {model_path}")
                return model_path
            else:
                raise FileNotFoundError(f"Local model not found: {model_path}")

        # Legacy HuggingFace repo format (for backwards compatibility)
        parts = model_path_or_repo.split("/")
        if len(parts) == 2:
            org, repo = parts
            quant = os.getenv("QUANTIZATION", "Q4_K_M")

            # Expected filename (strip -GGUF suffix, then append quantization)
            repo_base = repo.removesuffix("-GGUF").removesuffix("-gguf")
            filename = f"{repo_base}-{quant}.gguf"
            model_path = os.path.join(self.models_dir, filename)

            if os.path.exists(model_path):
                logger.info(f"Model already exists: {model_path}")
                return model_path

            # Download model
            logger.info(f"Downloading model: {model_path_or_repo}")
            os.makedirs(self.models_dir, exist_ok=True)

            import urllib.request

            url = f"https://huggingface.co/{model_path_or_repo}/resolve/main/{filename}"

            try:
                logger.info(f"Downloading from: {url}")
                urllib.request.urlretrieve(url, model_path)
                logger.info(f"Downloaded: {model_path}")
            except Exception as e:
                logger.error(f"Failed to download model: {e}")
                # Try alternative quantization
                for alt_quant in ["Q4_K_M", "Q5_K_M", "Q6_K", "Q8_0"]:
                    if alt_quant != quant:
                        alt_filename = f"{repo_base}-{alt_quant}.gguf"
                        alt_url = f"https://huggingface.co/{model_path_or_repo}/resolve/main/{alt_filename}"
                        try:
                            logger.info(f"Trying alternative: {alt_url}")
                            urllib.request.urlretrieve(alt_url, model_path)
                            logger.info(f"Downloaded alternative: {model_path}")
                            break
                        except:
                            continue

            if not os.path.exists(model_path):
                raise FileNotFoundError(
                    f"Could not download model: {model_path_or_repo}"
                )

            return model_path

        raise ValueError(
            f"Invalid model format: {model_path_or_repo}. Expected 'local/modelname' or 'org/repo'"
        )

    async def _wait_for_server(self, port: int, timeout: int = 60):
        """Wait for llama-server to be ready"""
        start_time = time.time()
        url = f"http://localhost:{port}/health"

        while time.time() - start_time < timeout:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=2) as response:
                        if response.status == 200:
                            return
            except:
                pass

            await asyncio.sleep(1)

        raise TimeoutError(f"Server on port {port} failed to start within {timeout}s")

    async def query_worker(
        self,
        worker_id: str,
        messages: List[Dict],
        temperature: float = 0.7,
        max_tokens: int = None,
        tools: List[Dict] = None,
    ) -> Dict:
        """Send query to a worker"""

        worker = self.workers.get(worker_id) or (
            self.judge if worker_id == "judge" else None
        )

        if not worker:
            raise ValueError(f"Worker {worker_id} not found")

        if worker["status"] != "running":
            raise RuntimeError(f"Worker {worker_id} is not running")

        url = f"http://localhost:{worker['port']}/v1/chat/completions"

        payload = {
            "model": worker["model_repo"],
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if tools:
            payload["tools"] = tools

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status != 200:
                    text = await response.text()
                    raise RuntimeError(f"Worker {worker_id} error: {text}")

                result = await response.json()

                # Check if response has valid choices
                if "choices" not in result or not result["choices"]:
                    logger.error(
                        f"Worker {worker_id} returned empty choices. Result: {result}"
                    )
                    raise RuntimeError(
                        f"Worker {worker_id} returned empty response - model may still be loading"
                    )

                choice = result["choices"][0]
                message = choice.get("message", {})

                # Extract relevant fields safely
                return {
                    "content": message.get("content", ""),
                    "tool_calls": message.get("tool_calls"),
                    "finish_reason": choice.get("finish_reason"),
                    "usage": result.get("usage", {}),
                    "model": result.get("model", worker["model_repo"]),
                }

    def get_available_workers(self) -> List[Dict]:
        """Get list of available workers"""
        return [
            {k: v for k, v in worker.items() if k != "process"}
            for worker in self.workers.values()
            if worker["status"] == "running"
        ]

    def get_worker_status(self) -> Dict[str, Any]:
        """Get status of all workers and judge"""
        return {
            "workers": {
                k: {
                    **{key: v for key, v in worker.items() if key != "process"},
                    "process_running": worker["process"] is not None
                    and worker["process"].poll() is None,
                }
                for k, worker in self.workers.items()
            },
            "judge": {
                **{k: v for k, v in self.judge.items() if k != "process"},
                "process_running": self.judge["process"] is not None
                and self.judge["process"].poll() is None,
            }
            if self.judge
            else None,
        }

    async def stop_all(self):
        """Stop all model servers"""
        logger.info("Stopping all model servers...")

        for worker_id, worker in self.workers.items():
            if worker["process"]:
                worker["process"].terminate()
                worker["status"] = "stopped"

        if self.judge and self.judge["process"]:
            self.judge["process"].terminate()
            self.judge["status"] = "stopped"

        # Wait for processes to terminate
        await asyncio.sleep(2)

        # Force kill if needed
        for worker in self.workers.values():
            if worker["process"] and worker["process"].poll() is None:
                worker["process"].kill()

        if (
            self.judge
            and self.judge["process"]
            and self.judge["process"].poll() is None
        ):
            self.judge["process"].kill()

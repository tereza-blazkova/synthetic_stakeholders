"""
Model backends and call logging.

Backends:
  OllamaBackend   a local model served by Ollama (http://localhost:11434)
  FakeBackend     no model: valid random answers from the JSON schema, for tests

Every call is appended to <run_dir>/calls.jsonl with the model id and digest, all
parameters, the full message list, the raw response, timestamps, token counts and
durations. Local runs cost no money, so "cost" is logged as compute time.
A run can be re-scored from calls.jsonl alone.
"""
from __future__ import annotations

import json
import random
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import os

# One Ollama server by default; on the multi-GPU UCloud job each family gets its
# own server (pinned to one GPU) via the OLLAMA_URL environment variable.
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


class CallLog:
    """Append-only JSONL log of every model call in one run."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.n = sum(1 for _ in path.open()) if path.exists() else 0

    def write(self, record: dict) -> None:
        self.n += 1
        with self.path.open("a") as f:
            f.write(json.dumps({"call_index": self.n, **record}, ensure_ascii=False) + "\n")


class OllamaBackend:
    """Chat completions from a local Ollama server, optionally constrained to a JSON schema."""

    def __init__(self, model: str, num_ctx: int = 16384, temperature: float = 1.0,
                 max_tokens: int = 4000, url: str = OLLAMA_URL, constrain: bool = False):
        self.model, self.url, self.constrain = model, url, constrain
        self.options = {"num_ctx": num_ctx, "temperature": temperature, "num_predict": max_tokens}
        info = self._post("/api/show", {"model": model})
        with urllib.request.urlopen(url + "/api/tags", timeout=60) as r:
            tags = json.loads(r.read())["models"]
        self.digest = next((m["digest"] for m in tags if m["name"] == model), None)
        self.capabilities = info.get("capabilities", [])
        self.model_info = {k: info.get("details", {}).get(k)
                           for k in ("family", "parameter_size", "quantization_level")}

    def unload_others(self) -> list[str]:
        """Unload every other model Ollama holds in memory (16 GB laptop: one at a time)."""
        with urllib.request.urlopen(self.url + "/api/ps", timeout=60) as r:
            loaded = [m["name"] for m in json.loads(r.read()).get("models", [])]
        others = [m for m in loaded if m != self.model]
        for m in others:
            self._post("/api/generate", {"model": m, "keep_alive": 0})
        return others

    def _post(self, path: str, body: dict, timeout: float = 3600) -> dict:
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())

    def chat(self, messages: list[dict], schema: dict | None, seed: int, extra: dict | None = None) -> dict:
        body = {"model": self.model, "messages": messages, "stream": False,
                "options": {**self.options, "seed": seed, **(extra or {})}, "keep_alive": "30m"}
        if "thinking" in self.capabilities:
            body["think"] = False          # same reasoning setting everywhere: off
        if schema is not None and self.constrain:     # off in this study (see workshop.py)
            body["format"] = schema
        r = self._post("/api/chat", body)
        return {"text": r["message"]["content"], "request": body,
                "usage": {"prompt_tokens": r.get("prompt_eval_count"),
                          "completion_tokens": r.get("eval_count"),
                          "prompt_seconds": (r.get("prompt_eval_duration") or 0) / 1e9,
                          "completion_seconds": (r.get("eval_duration") or 0) / 1e9,
                          "load_seconds": (r.get("load_duration") or 0) / 1e9}}


class FakeBackend:
    """Random but schema-valid answers; free text is a fixed placeholder. For tests only."""

    model, digest, capabilities, model_info = "fake", "fake", [], {}

    def __init__(self, *_, **__):
        pass

    def chat(self, messages: list[dict], schema: dict | None, seed: int, extra: dict | None = None) -> dict:
        rng = random.Random(seed)
        if schema is None:
            text = f"(fake turn, seed {seed})"
        else:
            out = {}
            for key, s in schema["properties"].items():
                if s["type"] == "string" and "enum" in s:
                    out[key] = rng.choice(s["enum"])
                elif s["type"] == "array":
                    out[key] = rng.sample(s["items"]["enum"], rng.randint(0, s.get("maxItems", 2)))
                else:
                    out[key] = ""
            text = json.dumps(out)
        return {"text": text, "request": {"model": "fake", "messages": messages, "seed": seed, "options": extra or {}},
                "usage": {"prompt_tokens": sum(len(m["content"]) // 4 for m in messages),
                          "completion_tokens": len(text) // 4,
                          "prompt_seconds": 0.0, "completion_seconds": 0.0, "load_seconds": 0.0}}


def logged_chat(backend, log: CallLog, *, messages: list[dict], schema: dict | None, extra: dict | None = None,
                seed: int, meta: dict) -> str:
    """Call the backend, log everything, return the response text."""
    started = datetime.now(timezone.utc).isoformat()
    t0 = time.monotonic()
    r = backend.chat(messages, schema, seed, extra)
    log.write({**meta, "model": backend.model, "model_digest": backend.digest,
               "model_info": backend.model_info, "started": started,
               "wall_seconds": round(time.monotonic() - t0, 3),
               "request": r["request"], "response": r["text"], "usage": r["usage"],
               "cost_usd": 0.0})
    return r["text"]

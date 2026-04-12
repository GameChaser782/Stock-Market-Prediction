from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AgentConfig:
    name: str = "supervisor"
    persona_text: str = "You are a helpful financial advisor."
    model_provider: str = "ollama"
    model_name: str = "qwen3.5"
    temperature: float = 0.7
    tools: list[str] = field(default_factory=list)
    memory_dir: str = ".portfolioiq"
    long_term_memory: bool = True
    thread_ttl: int = 3600
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    ollama_base_url: str = "http://localhost:11434"
    thinking: bool = False


def load_config(agent_name: str = "supervisor", config_dir: str = "agents") -> AgentConfig:
    """Load agent config from YAML + persona markdown, with env var overrides."""
    config_path = Path(config_dir) / f"{agent_name}.yaml"

    cfg: dict = {}
    if config_path.exists():
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}

    persona_text = "You are a helpful financial advisor."
    persona_file = cfg.get("persona", f"{agent_name}_persona.md")
    persona_path = Path(config_dir) / persona_file
    if persona_path.exists():
        persona_text = persona_path.read_text().strip()

    model_cfg = cfg.get("model", {})
    memory_cfg = cfg.get("memory", {})
    server_cfg = cfg.get("server", {})

    return AgentConfig(
        name=cfg.get("name", agent_name),
        persona_text=persona_text,
        model_provider=os.getenv("AGENT_PROVIDER", model_cfg.get("provider", "ollama")),
        model_name=os.getenv("AGENT_MODEL", model_cfg.get("name", "qwen3.5")),
        temperature=float(os.getenv("AGENT_TEMPERATURE", model_cfg.get("temperature", 0.7))),
        tools=cfg.get("tools", []),
        memory_dir=os.getenv("AGENT_MEMORY_DIR", memory_cfg.get("dir", ".portfolioiq")),
        long_term_memory=os.getenv("AGENT_LONG_TERM_MEMORY", str(memory_cfg.get("long_term", True))).lower() == "true",
        thread_ttl=int(memory_cfg.get("thread_ttl", 3600)),
        server_host=os.getenv("AGENT_SERVER_HOST", server_cfg.get("host", "0.0.0.0")),
        server_port=int(os.getenv("AGENT_SERVER_PORT", server_cfg.get("port", 8000))),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        thinking=os.getenv("AGENT_THINKING", str(model_cfg.get("thinking", False))).lower() == "true",
    )

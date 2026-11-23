import os
from dataclasses import dataclass
from pathlib import Path

from pydantic_ai.models.openai import OpenAIResponsesModelSettings


@dataclass(frozen=True)
class RuntimeSettings:
    state_dir: Path
    model: str = "openai-codex:gpt-6.2-sol"

    @classmethod
    def from_environment(cls) -> RuntimeSettings:
        data_home = Path(os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
        default = data_home / "Harness"
        legacy = data_home / "HarnessTest"
        if not (default / "harness.sqlite3").exists() and (legacy / "harness.sqlite3").exists():
            default = legacy
        return cls(
            Path(os.environ.get("HARNESS_STATE_DIR") or default).resolve(),
            os.environ.get("HARNESS_MODEL", cls.model),
        )


def model_settings(model: str) -> OpenAIResponsesModelSettings | None:
    if model.startswith("openai-codex:"):
        return OpenAIResponsesModelSettings(openai_reasoning_effort="medium")
    return None

from pathlib import Path
import os
import shutil
import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr

ROOT = Path(__file__).resolve().parents[4]

class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: SecretStr = SecretStr("")
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"
    vision_model: str | None = None
    maestro: str = str(ROOT / ".tools/maestro/bin/maestro.bat")
    adb: str = shutil.which("adb") or "D:/AndroidSDK/platform-tools/adb.exe"
    device: str | None = None
    app_id: str = "ru.natoday.app"
    repo: Path | None = ROOT
    artifacts: Path = ROOT / "artifacts/android-qa"
    max_steps: int = Field(100, ge=1, le=1000)
    timeout: float = Field(900, gt=0)
    max_calls: int = Field(120, ge=1)
    max_tokens: int = Field(200000, ge=100)
    response_tokens: int = Field(1800, ge=64, le=16000)
    api_timeout: float = Field(60, gt=0)
    tool_timeout: float = Field(90, gt=0)
    cleanup: str = "passed"
    profile: str = "baseline"

    def public(self):
        return self.model_dump(mode="json", exclude={"api_key"})

ENV = {"api_key": "DEEPSEEK_API_KEY", "base_url": "DEEPSEEK_BASE_URL", "model": "DEEPSEEK_MODEL", "vision_model": "DEEPSEEK_VISION_MODEL"}

def load(config: Path | None = None, env_file: Path | None = None, **overrides) -> Settings:
    data = yaml.safe_load(config.read_text(encoding="utf-8")) if config else {}
    if data is None: data = {}
    if not isinstance(data, dict): raise ValueError("Configuration must be a mapping")
    env = dict(dotenv_values(env_file)) if env_file else {}
    env.update(os.environ)
    for field in Settings.model_fields:
        name = ENV.get(field, "ANDROID_QA_" + field.upper())
        if env.get(name): data[field] = env[name]
    data.update({k: v for k, v in overrides.items() if v is not None})
    result = Settings.model_validate(data)
    if result.cleanup not in {"passed", "always", "never"}: raise ValueError("cleanup: passed|always|never")
    if result.profile not in {"baseline", "small", "large-font", "dark"}: raise ValueError("Unknown device profile")
    return result

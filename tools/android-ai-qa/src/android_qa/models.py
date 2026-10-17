from datetime import datetime, timezone
from typing import Literal, Any
from pydantic import BaseModel, ConfigDict, Field

def now(): return datetime.now(timezone.utc).isoformat()

class QAError(Exception):
    def __init__(self, category: str, message: str):
        self.category = category
        super().__init__(message)

class Element(BaseModel):
    index: int
    parent: int | None = None
    resource_id: str | None = None
    text: str | None = None
    description: str | None = None
    bounds: list[int] | None = None
    checked: bool | None = None
    enabled: bool | None = None
    clickable: bool | None = None
    focused: bool | None = None
    scrollable: bool | None = None
    selected: bool | None = None
    class_name: str | None = None

class Observation(BaseModel):
    observation_id: str
    timestamp: str = Field(default_factory=now)
    device: str
    package: str
    activity: str | None = None
    elements: list[Element]
    screenshot: str | None = None
    hierarchy: str
    fingerprint: str

class Check(BaseModel):
    name: str
    status: Literal["passed", "failed", "blocked", "not_checked"]
    expected: str
    actual: str
    evidence: list[str] = Field(default_factory=list)
    category: str = "functional"
    confidence: str = "confirmed"

class Action(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["tap", "input", "scroll", "back", "hide_keyboard", "restart", "check", "finish"]
    observation_id: str
    element: int | None = None
    text: str | None = None
    direction: Literal["UP", "DOWN"] = "DOWN"
    reason: str = Field(default="", max_length=300)

class Predicate(BaseModel):
    text: str
    present: bool = True
    checked: bool | None = None
    selected: bool | None = None
    exact: bool = True

class Milestone(BaseModel):
    name: str
    instruction: str
    predicates: list[Predicate]
    after_restart: bool = False
    full_list: bool = False

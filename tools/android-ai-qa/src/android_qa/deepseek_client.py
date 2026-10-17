import asyncio
import json
import httpx
from .models import QAError

class DeepSeek:
    def __init__(self, settings, transport=None):
        self.s = settings
        self.calls = self.tokens = self.reserved_tokens = 0
        self.usage_available = True
        self.client = httpx.AsyncClient(timeout=settings.api_timeout, transport=transport, follow_redirects=False)

    async def close(self): await self.client.aclose()

    async def complete(self, messages, tools=None, *, model=None):
        if not self.s.api_key.get_secret_value(): raise QAError("model", "DEEPSEEK_API_KEY is missing")
        payload = {"model": model or self.s.model, "messages": messages, "stream": False, "max_tokens": self.s.response_tokens, "thinking": {"type": "disabled"}}
        if tools: payload.update(tools=tools, tool_choice="auto")
        # A conservative byte bound is used when the API omits usage; not a price estimate.
        reservation = len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) + self.s.response_tokens
        for attempt in range(3):
            if self.calls >= self.s.max_calls or self.reserved_tokens + reservation > self.s.max_tokens:
                raise QAError("budget", "API request/token budget exhausted")
            self.calls += 1
            self.reserved_tokens += reservation
            try:
                r = await self.client.post(self.s.base_url.rstrip("/") + "/chat/completions", headers={"Authorization": "Bearer " + self.s.api_key.get_secret_value()}, json=payload)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if attempt < 2:
                    await asyncio.sleep(0.5 * 2**attempt)
                    continue
                raise QAError("model", "DeepSeek network/timeout failure") from exc
            if r.status_code == 429 or r.status_code >= 500:
                if attempt < 2:
                    retry = r.headers.get("retry-after", "")
                    await asyncio.sleep(min(float(retry), 10) if retry.isdigit() else 0.5 * 2**attempt)
                    continue
            if r.status_code != 200: raise QAError("model", f"DeepSeek HTTP {r.status_code}")
            try:
                data = r.json()
                usage = data.get("usage", {}).get("total_tokens")
                if isinstance(usage, int) and usage >= 0:
                    self.tokens += usage
                    self.reserved_tokens += usage - reservation
                else: self.usage_available = False
                choice = data["choices"][0]
                if choice["finish_reason"] not in {"stop", "tool_calls"}: raise ValueError("incomplete")
                message = choice["message"]
                # No chain of thought is retained, logged or forwarded.
                clean = {k: message[k] for k in ("role", "content", "tool_calls") if k in message}
                clean["role"] = "assistant"
                for call in clean.get("tool_calls", []):
                    if call["type"] != "function" or not isinstance(json.loads(call["function"]["arguments"]), dict): raise ValueError("tool call")
                return clean
            except (KeyError, IndexError, ValueError, TypeError) as exc:
                raise QAError("model", "Invalid or truncated DeepSeek response") from exc
        raise QAError("model", "DeepSeek unavailable")

    def usage(self):
        return {"calls": self.calls, "tokens_reported": self.tokens, "budget_tokens": self.reserved_tokens, "usage_available": self.usage_available}

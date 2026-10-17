import asyncio
import base64
import json
import os
from pathlib import Path
from contextlib import asynccontextmanager
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from jsonschema import validate
from .models import QAError

class Maestro:
    def __init__(self, session, tools, settings, report=None):
        self.session, self.tools, self.s, self.report = session, tools, settings, report
        # Known official protocol versions only, verified against tools/list.
        candidates = {"devices": ("list_devices",), "tree": ("inspect_screen", "inspect_view_hierarchy"), "screenshot": ("take_screenshot",), "run": ("run", "run_flow"), "help": ("cheat_sheet",)}
        self.capabilities = {k: next((n for n in names if n in tools), None) for k,names in candidates.items()}
        for k in ("devices", "tree", "screenshot", "run"):
            if not self.capabilities[k]: raise QAError("tool", "Official Maestro MCP capability missing: " + k)

    @classmethod
    @asynccontextmanager
    async def connect(cls, settings, report=None):
        path = Path(settings.maestro)
        if not path.exists(): raise QAError("environment", "Maestro binary missing: " + str(path))
        env = {k: v for k,v in os.environ.items() if k in {"PATH", "SystemRoot", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "COMSPEC", "JAVA_HOME", "ANDROID_HOME", "ANDROID_SDK_ROOT"}}
        env.update(MAESTRO_CLI_NO_ANALYTICS="true", MAESTRO_CLI_ANALYTICS_ENABLED="false", JAVA_HOME=os.environ.get("JAVA_HOME", "D:/Java"), ANDROID_HOME=os.environ.get("ANDROID_HOME", "D:/AndroidSDK"))
        args = ["mcp"]
        params = StdioServerParameters(command=str(path), args=args, env=env, cwd=str(path.parent))
        log = (report.path / "logs/maestro-stderr.log").open("w", encoding="utf-8") if report else open(os.devnull, "w")
        try:
            async with stdio_client(params, errlog=log) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=settings.tool_timeout) as session:
                    async with asyncio.timeout(settings.tool_timeout):
                        init = await session.initialize()
                        discovery = await session.list_tools()
                    tools = {t.name: t.model_dump(mode="json", by_alias=True) for t in discovery.tools}
                    client = cls(session, tools, settings, report)
                    if report:
                        report.json("mcp-tools.json", tools)
                        report.metadata.update(real_mcp=True, mcp_server=init.model_dump(mode="json", by_alias=True), mcp_capabilities=client.capabilities)
                    yield client
        finally:
            log.close()

    async def call(self, capability, **values):
        name = self.capabilities.get(capability)
        if not name: raise QAError("tool", "Unsupported capability: " + capability)
        schema = self.tools[name]["inputSchema"]
        props = schema.get("properties", {})
        args = {}
        for key in ("device_id", "deviceId", "device"):
            if key in props and self.s.device: args[key] = self.s.device
        for key,value in values.items():
            if key in props: args[key] = value
            elif key == "yaml" and "flow_yaml" in props: args["flow_yaml"] = value
            else: raise QAError("tool", f"Unsupported {name} argument: {key}")
        try: validate(args, schema)
        except Exception as exc: raise QAError("tool", f"MCP argument schema mismatch: {name}") from exc
        if self.report: self.report.event("mcp_call", tool=name, arguments=args)
        try:
            async with asyncio.timeout(self.s.tool_timeout):
                result = await self.session.call_tool(name, args)
        except TimeoutError as exc: raise QAError("tool_timeout", f"MCP {name} timed out; outcome unknown") from exc
        error = getattr(result, "is_error", getattr(result, "isError", False))
        texts, images = [], []
        for block in result.content:
            if block.type == "text": texts.append(block.text)
            elif block.type == "image": images.append({"data": block.data, "mime_type": block.mime_type})
        if self.report: self.report.event("mcp_result", tool=name, is_error=error, text="\n".join(texts)[:12000], image_count=len(images))
        if error: raise QAError("tool", f"MCP {name}: " + "\n".join(texts)[:1000])
        if capability=="run":
            for txt in texts:
                try: payload=json.loads(txt)
                except ValueError: continue
                if isinstance(payload,dict) and payload.get("success") is False:
                    raise QAError("tool", "Maestro flow failed: "+txt[:1200])
        structured = getattr(result, "structured_content", None)
        return {"structured": structured, "text": "\n".join(texts), "images": images}

    async def run(self, yaml): return await self.call("run", yaml=yaml)

    async def screenshot(self, destination):
        result = await self.call("screenshot")
        if result["images"]:
            destination.write_bytes(base64.b64decode(result["images"][0]["data"], validate=True))
            return True
        return False

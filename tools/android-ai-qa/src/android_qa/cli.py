import asyncio
import json
import sys
from pathlib import Path
from typing import Optional
import typer
from .config import load,ROOT
from .models import QAError,Check
from .diagnostics import basics,command,adb,select_device
from .maestro_client import Maestro
from .deepseek_client import DeepSeek
from .reports import Report
from .capabilities import probe_api
from .agent import run_scenario,replay as replay_run,unwrap
from .file_tools import Files
from .scenarios import SOURCE_FILES
from .flow_exporter import load_flow

app=typer.Typer(help="Local Android AI QA — DeepSeek + official Maestro MCP",no_args_is_help=True)
SCENARIOS={"create","move","status","delete","lifecycle","undo","empty-title","long-title","keyboard"}

def settings(config,env_file,device=None,app_id=None,repo=None,**kwargs):
    return load(config,env_file,device=device,app_id=app_id,repo=repo,**kwargs)

def execute(coro):
    try: return asyncio.run(coro)
    except KeyboardInterrupt: raise typer.Exit(130)
    except Exception as raw:
        exc=unwrap(raw)
        typer.echo(f"ERROR: {exc}",err=True)
        raise typer.Exit(2)

def capabilities(s):
    path=s.artifacts/"capabilities.json"
    if path.exists():
        data=json.loads(path.read_text(encoding="utf-8"))
        if data.get("model")==s.model and data.get("vision_model")==s.vision_model and data.get("base_url")==s.base_url: return data["capabilities"]
    return {}

@app.command()
def doctor(check_api:bool=False,device:Optional[str]=None,app_id:Optional[str]=None,config:Optional[Path]=None,env_file:Optional[Path]=None,model:Optional[str]=None,vision_model:Optional[str]=None,maestro:Optional[str]=None):
    """Check local prerequisites. --check-api performs paid API requests."""
    s=settings(config,env_file,device,app_id,model=model,vision_model=vision_model,maestro=maestro)
    async def go():
        report=Report(s.artifacts,"Environment and capability diagnostics",s,"doctor")
        data=await basics(s)
        try:
            code,out,err=await command([s.maestro,"--version"])
            data["maestro"]={"ok":code==0,"version":out or err}
            async with Maestro.connect(s,report) as m:
                data["mcp"]={"ok":True,"capabilities":m.capabilities,"devices":(await m.call("devices"))["text"]}
                sheet=await m.call("help")
                (report.path/"maestro-cheatsheet.md").write_text(sheet["text"],encoding="utf-8")
        except Exception as raw:
            data["mcp"]={"ok":False,"reason":str(unwrap(raw)),"fix":"Windows: unpack official maestro.zip under .tools/maestro, use Java 17+ and set ANDROID_QA_MAESTRO. No automatic elevated installation."}
        if check_api:
            typer.echo("Network checks use DeepSeek API quota (text, tool calling, image, image + tools).")
            llm=DeepSeek(s)
            try:
                caps=await probe_api(llm);data["api"]=caps
                s.artifacts.mkdir(parents=True,exist_ok=True)
                (s.artifacts/"capabilities.json").write_text(json.dumps({"model":s.model,"vision_model":s.vision_model,"base_url":s.base_url,"capabilities":caps},indent=2),encoding="utf-8")
                report.metadata["usage"]=llm.usage()
                report.metadata["real_deepseek"]=llm.calls>0
            finally: await llm.close()
        data["api_checks_requested"]=check_api
        report.json("doctor.json",data)
        required=data.get("app_installed") and data.get("mcp",{}).get("ok") and not data.get("device_error") and data["api_key_present"]
        if check_api: required=required and all(data.get("api",{}).get(k,{}).get("supported") for k in ("text","tools"))
        report.finish("passed" if required else "blocked",diagnostics=data)
        typer.echo(json.dumps(data,ensure_ascii=False,indent=2))
        typer.echo("REPORT "+str(report.path/"report.md"))
        return bool(required)
    if not execute(go()): raise typer.Exit(2)

@app.command("install-apk")
def install_apk(apk:Path=typer.Option(...,exists=True),device:str=typer.Option(...),config:Optional[Path]=None):
    """Explicit installation, preserving existing data; never invoked by run."""
    s=settings(config,None,device)
    async def go():
        await select_device(s)
        typer.echo(await adb(s,"install","-r",str(apk.resolve()),timeout=120))
    execute(go())

@app.command()
def run(goal:str=typer.Option(...),device:Optional[str]=None,app_id:Optional[str]=None,repo:Optional[Path]=None,config:Optional[Path]=None,env_file:Optional[Path]=None,scenario:Optional[str]=None,cleanup:Optional[str]=None,max_steps:Optional[int]=None,timeout:Optional[float]=None,profile:Optional[str]=None,black_box:bool=False,model:Optional[str]=None,vision_model:Optional[str]=None,maestro:Optional[str]=None,artifacts:Optional[Path]=None,max_calls:Optional[int]=None,max_tokens:Optional[int]=None):
    """Explore an app and satisfy the goal; export and replay verified actions."""
    s=settings(config,env_file,device,app_id,repo,cleanup=cleanup,max_steps=max_steps,timeout=timeout,profile=profile,model=model,vision_model=vision_model,maestro=maestro,artifacts=artifacts,max_calls=max_calls,max_tokens=max_tokens)
    if black_box: s.repo=None
    async def go():
        chosen=scenario
        planning_usage=None
        if chosen is None:
            llm=DeepSeek(s)
            tool={"type":"function","function":{"name":"select_scenario","description":"Choose the smallest scenario satisfying the user's goal. Each includes independent task creation.","parameters":{"type":"object","properties":{"scenario":{"type":"string","enum":["create","move","status","delete","lifecycle","undo"]}},"required":["scenario"]}}}
            try:
                reply=await llm.complete([{"role":"system","content":"Map the goal to a supported task-list QA scenario by calling select_scenario. move includes creation. lifecycle includes all four operations."},{"role":"user","content":goal}],[tool])
                call=reply.get("tool_calls",[])
                if len(call)!=1 or call[0]["function"]["name"]!="select_scenario": raise QAError("requirements","Goal needs a supported scenario")
                chosen=json.loads(call[0]["function"]["arguments"])["scenario"]
            finally:
                planning_usage=llm.usage()
                await llm.close()
        if chosen not in SCENARIOS: raise QAError("requirements","Unknown scenario")
        return await run_scenario(s,goal,chosen,capabilities(s),planning_usage)
    report=execute(go())
    if report.metadata["status"]!="passed": raise typer.Exit(2)

@app.command()
def suite(device:Optional[str]=None,app_id:Optional[str]=None,repo:Optional[Path]=None,config:Optional[Path]=None,env_file:Optional[Path]=None,scenario:Optional[str]=None,cleanup:Optional[str]=None):
    """Independent create, move, status, delete; optional lifecycle/undo."""
    s=settings(config,env_file,device,app_id,repo,cleanup=cleanup)
    scenarios=[scenario] if scenario else ["create","move","status","delete"]
    if any(x not in SCENARIOS for x in scenarios): raise typer.BadParameter("Unknown scenario")
    async def go():
        results=[]
        for name in scenarios:
            report=await run_scenario(s,"Проверь сценарий "+name,name,capabilities(s))
            results.append({"scenario":name,"status":report.metadata["status"],"report":str(report.path),"flow":report.metadata.get("flow")})
        s.artifacts.mkdir(parents=True,exist_ok=True)
        (s.artifacts/"suite-latest.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
        typer.echo(json.dumps(results,ensure_ascii=False,indent=2))
        return all(r["status"]=="passed" for r in results)
    if not execute(go()): raise typer.Exit(2)

@app.command()
def replay(flow:Path=typer.Option(...,exists=True),device:Optional[str]=None,app_id:Optional[str]=None,config:Optional[Path]=None):
    s=settings(config,None,device,app_id)
    report=execute(replay_run(s,flow))
    typer.echo("REPORT "+str(report.path/"report.md"))
    if report.metadata["status"]!="passed": raise typer.Exit(2)

@app.command()
def web(device:str=typer.Option(...),port:int=8765,app_id:Optional[str]=None,config:Optional[Path]=None,env_file:Optional[Path]=None,repo:Optional[Path]=None):
    """Serve the local scenario dashboard on 127.0.0.1."""
    s=settings(config,env_file,device,app_id,repo)
    from .web import serve
    try: serve(s,port)
    except (OSError,ValueError) as exc:
        typer.echo(f"ERROR: {exc}",err=True)
        raise typer.Exit(2)

@app.command()
def generate(goal:str=typer.Option(...),repo:Path=ROOT,config:Optional[Path]=None,env_file:Optional[Path]=None):
    """Mode A: research source/docs/tests and draft an UNVERIFIED flow."""
    s=settings(config,env_file,repo=repo)
    async def go():
        report=Report(s.artifacts,goal,s,"generate");fs=Files(repo,report)
        hits=fs.search(goal+" task move create delete status")
        paths=list(dict.fromkeys([h["path"] for h in hits]+SOURCE_FILES))
        source=[]
        for path in paths[:8]:
            try: source.append(fs.read(path,1,150))
            except (QAError,OSError): pass
        if len(source)<3: raise QAError("requirements","At least three relevant source files required")
        llm=DeepSeek(s)
        try:
            reply=await llm.complete([{"role":"system","content":"Create a plain Maestro YAML flow from the goal and evidence. Return YAML only. appId: ${APP_ID}. Input task title: ${TASK_NAME}. Only launchApp(clearState false), tapOn, inputText, hideKeyboard, back, scroll, assertVisible, assertNotVisible, extendedWaitUntil. No scripts, coordinates if selectors exist, cloud, accounts or clearState. Include functional assertions. Do not assert test execution."},{"role":"user","content":json.dumps({"goal":goal,"sources":source},ensure_ascii=False)}])
            text=(reply.get("content") or "").strip()
            if text.startswith("```"): text="\n".join(text.splitlines()[1:-1])
            load_flow(text,{"APP_ID":s.app_id,"TASK_NAME":"AIQA-draft-create"})
            path=repo/"qa/flows"/("draft-"+report.id+".yaml");path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding="utf-8")
            report.finish("unverified",flow={"path":str(path.resolve()),"status":"unverified","reason":"Generated from code; no replay"},usage=llm.usage(),real_deepseek=True,source_analysis={"files":len(source),"minimum_met":len(source)>=3})
            typer.echo(str(path))
        except Exception as exc:
            report.finish("blocked",error=str(exc),usage=llm.usage())
            raise
        finally: await llm.close()
    execute(go())

@app.command("docs-diff")
def docs_diff(report:Path=typer.Option(...,exists=True),repo:Path=ROOT):
    """Mode B: propose a QA documentation update based on actual checks."""
    fs=Files(repo);checks=json.loads((report/"checks.json").read_text(encoding="utf-8"))
    target="qa/verification.md";path=fs.checked(target,write=True)
    original=path.read_text(encoding="utf-8") if path.exists() else "# QA verification\n"
    content=original+"\n## Run "+report.name+"\n\n"+"\n".join(f"- {c['name']}: {c['status']} — {c['actual']}" for c in checks)+"\n"
    typer.echo(fs.stage(target,content,report/"proposals"))

@app.command("docs-apply")
def docs_apply(report:Path=typer.Option(...,exists=True),repo:Path=ROOT):
    """Explicit apply of reviewed QA diff with hash and dirty-state checks."""
    try: typer.echo(Files(repo).apply(report/"proposals"))
    except QAError as exc: typer.echo(str(exc),err=True);raise typer.Exit(2)

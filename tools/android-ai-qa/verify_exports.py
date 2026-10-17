"""Normalize real suite traces, replay without LLM, publish only verified new files."""
import asyncio
from datetime import date,timedelta
import json
from pathlib import Path
import sys
from android_qa.config import Settings,ROOT
from android_qa.reports import Report
from android_qa.flow_exporter import load_flow,export
from android_qa.agent import replay
from android_qa.scenarios import label,calendar_label

async def main():
    s=Settings(device="emulator-5554")
    suite=json.loads((s.artifacts/"suite-latest.json").read_text(encoding="utf-8"))
    names={"create":"create-task","move":"move-task","status":"change-status","delete":"delete-task"}
    verified=[]
    for item in suite:
        source=Path(item["report"])
        meta=json.loads((source/"run.json").read_text(encoding="utf-8"))
        today=date.fromisoformat(meta["device"]["date"]);tomorrow=today+timedelta(days=1)
        values={"SOURCE_DATE_LABEL":label(today),"TARGET_DATE_LABEL":label(tomorrow),"TARGET_CALENDAR_DATE":calendar_label(tomorrow)}
        commands=load_flow(Path(meta["flow"]["path"]).read_text(encoding="utf-8"),{"APP_ID":s.app_id,"TASK_NAME":meta["task_name"],**values})
        normalized=[]
        for cmd in commands:
            normalized.append(cmd)
            if isinstance(cmd,dict) and cmd.get("assertVisible",{}).get("text")==meta["task_name"]:
                normalized.append({"assertNotVisible":{"text":meta["task_name"],"index":1}})
        report=Report(s.artifacts,"Normalize and verify exported "+item["scenario"],s,"export")
        flow=export(report,s.app_id,normalized,meta["task_name"],item["scenario"],values)
        result=await replay(s,flow,scenario=item["scenario"])
        ok=result.metadata["status"]=="passed"
        report.metadata["flow"].update(status="verified" if ok else "unverified",reason=result.metadata.get("error"),replay_report=str(result.path))
        report.finish("passed" if ok else "blocked",source_report=str(source))
        if ok:
            destination=ROOT/"qa/flows"/(names[item["scenario"]]+".yaml")
            if destination.exists(): raise RuntimeError("Refusing to overwrite existing flow: "+str(destination))
            destination.write_text(flow.read_text(encoding="utf-8"),encoding="utf-8")
            sidecar={"status":"verified","source_report":str(source),"replay_report":str(result.path),"normalization_report":str(report.path),"device":"emulator-5554","maestro":"2.11.0"}
            destination.with_suffix(".verification.json").write_text(json.dumps(sidecar,ensure_ascii=False,indent=2),encoding="utf-8")
        verified.append({"scenario":item["scenario"],"verified":ok,"report":str(result.path)})
        print(json.dumps(verified[-1],ensure_ascii=False),flush=True)
    (s.artifacts/"verified-exports.json").write_text(json.dumps(verified,ensure_ascii=False,indent=2),encoding="utf-8")
    return all(x["verified"] for x in verified)

if __name__=="__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(0 if asyncio.run(main()) else 1)

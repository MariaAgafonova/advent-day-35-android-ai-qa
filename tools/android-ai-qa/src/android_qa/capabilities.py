import base64
import io
import json
from PIL import Image,ImageDraw
from .models import QAError,Check

PROBE_TOOL={"type":"function","function":{"name":"probe_result","description":"Return the requested result","parameters":{"type":"object","properties":{"answer":{"type":"string"}},"required":["answer"],"additionalProperties":False}}}

async def probe_api(client):
    result={}
    tests=[("text",[{"role":"user","content":"Reply OK."}],None,client.s.model), ("tools",[{"role":"user","content":"Call probe_result with answer OK."}],[PROBE_TOOL],client.s.model)]
    picture=Image.new("RGB",(64,64),"red")
    buf=io.BytesIO();picture.save(buf,format="PNG")
    content=[{"type":"text","text":"What single color fills this image?"},{"type":"image_url","image_url":{"url":"data:image/png;base64,"+base64.b64encode(buf.getvalue()).decode()}}]
    vision=client.s.vision_model or client.s.model
    tests += [("vision",[{"role":"user","content":content}],None,vision),("vision_tools",[{"role":"user","content":[{**content[0],"text":"Call probe_result with the single color that fills the image."},content[1]]}],[PROBE_TOOL],vision)]
    for name,messages,tools,model in tests:
        try:
            reply=await client.complete(messages,tools,model=model)
            if tools:
                calls=reply.get("tool_calls",[])
                if len(calls)!=1 or calls[0]["function"]["name"]!="probe_result": raise QAError("model","Expected probe tool call missing")
                answer=json.loads(calls[0]["function"]["arguments"])["answer"]
                # Verify the second turn with an actual matching tool result.
                await client.complete([*messages,reply,{"role":"tool","tool_call_id":calls[0]["id"],"content":json.dumps({"accepted":True})}],tools,model=model)
            else: answer=reply.get("content","")
            ok = ("red" in answer.lower() or "крас" in answer.lower()) if "vision" in name else "ok" in answer.lower()
            result[name]={"supported":ok,"model":model,"reason":"probe passed" if ok else "incorrect probe answer"}
        except QAError as exc: result[name]={"supported":False,"model":model,"reason":str(exc)}
    return result

async def visual_check(client,observation,report,capabilities):
    if not capabilities.get("vision",{}).get("supported") or not observation.screenshot:
        report.add(Check(name="visual_layout",status="not_checked",expected="Inspect clipping, keyboard coverage, readable dialog and action reachability",actual="Vision capability unavailable or screenshot missing; hierarchy bounds alone are insufficient",category="capability",evidence=[observation.hierarchy]))
        return
    picture=Image.open(report.path/observation.screenshot).convert("RGB");picture.thumbnail((512,768))
    buf=io.BytesIO();picture.save(buf,format="JPEG",quality=75)
    reply=await client.complete([{"role":"system","content":"Inspect Android UI for visible clipping or keyboard covering required actions. Do not infer dp, contrast, or bug causes. Return JSON with observations (array of strings) and suspects (array of strings). All findings are preliminary; do not claim a confirmed defect."},{"role":"user","content":[{"type":"text","text":"Inspect this screenshot. UI context: "+json.dumps([e.model_dump(exclude_none=True) for e in observation.elements if e.text or e.description],ensure_ascii=False)[:5000]},{"type":"image_url","image_url":{"url":"data:image/jpeg;base64,"+base64.b64encode(buf.getvalue()).decode()}}]}],model=client.s.vision_model or client.s.model)
    report.json("visual-"+observation.observation_id+".json",{"observation_id":observation.observation_id,"assessment":reply.get("content"),"confirmation":"preliminary"})
    report.add(Check(name="visual_"+observation.observation_id,status="not_checked",expected="Confirmed visual correctness",actual="AI visual assessment saved; requires confirmation against product requirements",evidence=[observation.screenshot,"visual-"+observation.observation_id+".json"],category="visual",confidence="preliminary"))

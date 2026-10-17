import pytest
from types import SimpleNamespace
from android_qa.flow_exporter import export,load_flow,validate_replay_ownership
from android_qa.models import QAError

def seed():
    return [{"inputText":"AIQA-new"},{"assertVisible":{"text":"AIQA-new"}},{"assertVisible":{"text":"Сегодня"}},{"assertNotVisible":{"text":"error"}}]

def test_replay_old_task_denied():
    with pytest.raises(QAError):validate_replay_ownership(seed()+[{"tapOn":{"text":"Действия с задачей «AIQA-old»"}},{"tapOn":{"text":"Удалить"}}],"AIQA-new")

def test_replay_delete_needs_context():
    with pytest.raises(QAError):validate_replay_ownership(seed()+[{"tapOn":{"text":"Удалить"}}],"AIQA-new")

def test_replay_delete_owned():
    validate_replay_ownership(seed()+[{"tapOn":{"text":"Действия с задачей «AIQA-new»"}},{"tapOn":{"text":"Удалить"}}],"AIQA-new")

def test_replay_requires_assertions():
    with pytest.raises(QAError):validate_replay_ownership([{"inputText":"AIQA-new"}],"AIQA-new")

def test_replay_no_coordinates():
    with pytest.raises(QAError):validate_replay_ownership(seed()+[{"tapOn":{"point":"1,2"}}],"AIQA-new")

def test_conditional_cannot_delete():
    commands=seed()+[{"runFlow":{"when":{"visible":"x"},"commands":[{"tapOn":{"text":"Удалить"}}]}}]
    with pytest.raises(QAError):validate_replay_ownership(commands,"AIQA-new")

@pytest.mark.parametrize(("calendar_text","target"),[
    ("воскресенье, 18 октября\u202fг.","18 октября"),
    ("понедельник, 1 января 2029\u202fг.","1 января"),
])
def test_export_calendar_date_ignores_localized_weekday(tmp_path,calendar_text,target):
    report=SimpleNamespace(path=tmp_path,metadata={},save=lambda:None)
    source=[{"tapOn":{"text":calendar_text}}]
    path=export(report,"ru.natoday.app",source,"AIQA-new","move",{"TARGET_CALENDAR_DATE":target})
    text=path.read_text(encoding="utf-8")
    assert "воскресенье" not in text and "понедельник" not in text
    assert ".*${TARGET_CALENDAR_DATE}.*" in text
    commands=load_flow(text,{"APP_ID":"ru.natoday.app","TASK_NAME":"AIQA-new","TARGET_CALENDAR_DATE":target})
    assert commands[1]["tapOn"]["text"]==".*"+target+".*"

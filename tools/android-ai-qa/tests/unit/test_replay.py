import pytest
from android_qa.flow_exporter import validate_replay_ownership
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

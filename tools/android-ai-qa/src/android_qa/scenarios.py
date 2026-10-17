from datetime import date,timedelta
from .models import Milestone,Predicate

MONTHS="января февраля марта апреля мая июня июля августа сентября октября ноября декабря".split()
DAYS="понедельник вторник среда четверг пятница суббота воскресенье".split()
def label(d): return f"{d.day} {MONTHS[d.month-1]} {d.year}, {DAYS[d.weekday()]}"
def calendar_label(d): return f"{d.day} {MONTHS[d.month-1]} {d.year}"

def milestones(scenario,task,today):
    tomorrow=today+timedelta(days=1)
    def datep(d): return Predicate(text=label(d))
    def title(present=True): return Predicate(text=task,present=present)
    def status(done=False): return Predicate(text=("Отменить выполнение" if done else "Выполнить")+f" «{task}»",checked=done)
    def ms(name,instruction,predicates,restart=False,full=False): return Milestone(name=name,instruction=instruction,predicates=predicates,after_restart=restart,full_list=full)
    steps=[ms("created","Создай ОДНУ задачу с точным назначенным именем на сегодня; проверь дату и начальный статус. Закрой редактор.",[datep(today),title(),status()],full=True)]
    if scenario in {"create","long-title","keyboard","empty-title"}:
        steps.append(ms("create_persisted","Перезапусти приложение через restart и проверь задачу на сегодня.",[datep(today),title(),status()],True,True))
    if scenario=="empty-title":
        steps.insert(0,ms("empty_rejected","Открой Добавить задачу и нажми Сохранить с пустым полем. Ничего не вводи. Проверь сообщение ошибки; редактор остаётся открытым.",[Predicate(text="Напишите название задачи"),Predicate(text="Что нужно сделать?")]))
    if scenario=="keyboard":
        steps[0].instruction+=" Сохрани при ОТКРЫТОЙ клавиатуре, не вызывай hide_keyboard/Back до сохранения."
    if scenario in {"move","lifecycle"}:
        steps += [ms("move_source_absent","Перенеси собственную задачу через меню и календарь на завтра "+tomorrow.isoformat()+". Подтверди Сохранить. Останься на исходной дате и проверь отсутствие.",[datep(today),title(False)],full=True),ms("move_target_present","Перейди на завтрашний день и проверь название и неизменный статус.",[datep(tomorrow),title(),status()],full=True),ms("move_persisted","Перезапусти приложение; снова открой завтрашнюю дату и проверь сохранение переноса.",[datep(tomorrow),title(),status()],True,True)]
    current=tomorrow if scenario=="lifecycle" else today
    if scenario in {"status","lifecycle"}:
        steps += [ms("completed","Отметь собственную задачу выполненной и раскрой раздел Выполненные.",[datep(current),title(),status(True)]),ms("status_persisted","Перезапусти приложение; открой нужную дату и раздел Выполненные. Проверь checked=true.",[datep(current),title(),status(True)],True),ms("status_reversed","Верни собственную задачу в невыполненные. Проверь checked=false.",[datep(current),title(),status()])]
    if scenario in {"delete","lifecycle"}:
        steps += [ms("deleted","Удали собственную задачу через её меню. Диалога подтверждения в этом приложении нет; Undo проверяется отдельно.",[datep(current),title(False)],full=True),ms("delete_persisted","Перезапусти приложение; открой исходную дату задачи и проверь, что она не появилась.",[datep(current),title(False)],True,True)]
    if scenario=="undo":
        steps += [ms("undo_available","Удали собственную задачу и проверь наличие Snackbar Отменить.",[Predicate(text="Отменить"),title(False)]),ms("undo_restored","Нажми Отменить в Snackbar и проверь восстановление задачи.",[datep(today),title(),status()])]
    return steps

SOURCE_FILES=["docs/app/original-readme.md","app/src/main/java/ru/natoday/app/ui/DayScreen.kt","app/src/main/java/ru/natoday/app/ui/Components.kt","app/src/main/java/ru/natoday/app/data/TaskRepository.kt","app/src/androidTest/java/ru/natoday/app/PlannerUiTest.kt"]

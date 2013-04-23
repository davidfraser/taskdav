#!/usr/bin/env python

"""todo.txt command-line compatibility - implements many commands from todo.txt"""

from taskdav.task import Task, TaskDAVClient
from datetime import datetime
import caldav
import re
import uuid
import aaargh
import config

cfg = config.get_config()
url = cfg.get('server', 'url').replace("://", "://%s:%s@" % (cfg.get('server', 'username'), cfg.get('server', 'password'))) + "dav/%s/" % (cfg.get('server', 'username'),)
client = TaskDAVClient(url)

utc = caldav.vobject.icalendar.utc

app = aaargh.App(description="A simple command-line tool for interacting with Tasks over CalDAV")

app.arg('-n', '--calendar-name', help="Name of the calendar to use", default="Tasks")

def alias(name, alias_name):
    """Adds an alias to the given command name"""
    # TODO: if https://github.com/wbolster/aaargh/pull/4 is accepted, replace this with alias= arguments
    parser_map = app._parser._subparsers._group_actions[0]._name_parser_map
    parser_map[alias_name] = parser_map[name]

@app.cmd(name="list", help="Displays all incomplete tasks containing the given search terms (if any) either as ID prefix or summary text; a term like test- ending with a - is a negative search")
@app.cmd_arg('term', type=str, nargs='*', help="Search terms")
def list_(calendar_name, term):
    task_lookup = client.get_tasks(calendar_name)
    # TODO: make lookup by known ID not have to load all tasks
    term = [t.lower() for t in term]
    for task_id in sorted(task_lookup):
        task = client.get_task(calendar_name, task_id)
        if task.todo_attr("status") != "COMPLETED":
            search_text = task.todo_attr("summary").lower()
            if all(task.id.startswith(t) or (t[:-1] not in search_text if t.endswith('-') else t in search_text) for t in term):
                print task_lookup.shortest(task_id), task.format()

alias("list", "ls")

@app.cmd(help="Displays all tasks containing the given search terms (if any) either as ID prefix or summary text; a term like test- ending with a - is a negative search")
@app.cmd_arg('term', type=str, nargs='*', help="Search terms")
def listall(calendar_name, term):
    task_lookup = client.get_tasks(calendar_name)
    # TODO: make lookup by known ID not have to load all tasks
    term = [t.lower() for t in term]
    for task_id in sorted(task_lookup):
        task = client.get_task(calendar_name, task_id)
        search_text = task.todo_attr("summary").lower()
        if all(task.id.startswith(t) or (t[:-1] not in search_text if t.endswith('-') else t in search_text) for t in term):
            print task_lookup.shortest(task_id), task.format()

alias("listall", "lsa")

@app.cmd(help="Reports on the number of open and done tasks")
def report(calendar_name):
    date = datetime.utcnow().replace(tzinfo=utc)
    task_lookup = client.get_tasks(calendar_name)
    task_status_count = {}
    for task_id in sorted(task_lookup):
        task = client.get_task(calendar_name, task_id)
        status = task.todo_attr("status")
        task_status_count[status] = task_status_count.get(status, 0) + 1
    print date
    for status in sorted(task_status_count):
        print status, task_status_count[status]

@app.cmd(help="Displays all incomplete tasks of the given (or any) priority containing the given search terms (if any) either as ID prefix or summary text; a term like test- ending with a - is a negative search")
@app.cmd_arg('priority', type=str, nargs='?', help="Priority")
@app.cmd_arg('term', type=str, nargs='*', help="Search terms")
def listpri(calendar_name, priority, term):
    try:
        priorities = Task.parse_priority_range(priority)
    except ValueError:
        # Assume this wasn't really a priority
        term.insert(0, priority)
        priorities = Task.ALL_PRIORITIES
    task_lookup = client.get_tasks(calendar_name)
    term = [t.lower() for t in term]
    for task_id in sorted(task_lookup):
        task = client.get_task(calendar_name, task_id)
        if task.todo_attr("status") != "COMPLETED" and int(task.todo_attr("priority", "") or "0") in priorities:
            search_text = task.todo_attr("summary").lower()
            if all(task.id.startswith(t) or (t[:-1] not in search_text if t.endswith('-') else t in search_text) for t in term):
                print task_lookup.shortest(task_id), task.format()

alias("listpri", "lsp")

CONTEXT_RE = re.compile(r'(?:^|\s)(@\w*\b)')

@app.cmd(help="Lists all the task contexts that start with the @ sign in task summaries")
def listcon(calendar_name):
    task_lookup = client.get_tasks(calendar_name)
    contexts = set()
    for task_id in task_lookup:
        task = client.get_task(calendar_name, task_id)
        if task.todo_attr("status") != "COMPLETED":
            summary = task.todo_attr("summary")
            contexts.update(CONTEXT_RE.findall(summary))
    for context in sorted(contexts):
        print context

alias("listcon", "lsc")

PROJ_RE = re.compile(r'(?:^|\s)(\+\w*\b)')

@app.cmd(help="Lists all the task projects that start with the + sign in task summaries")
def listproj(calendar_name):
    task_lookup = client.get_tasks(calendar_name)
    projects = set()
    for task_id in task_lookup:
        task = client.get_task(calendar_name, task_id)
        if task.todo_attr("status") != "COMPLETED":
            summary = task.todo_attr("summary")
            projects.update(PROJ_RE.findall(summary))
    for project in sorted(projects):
        print project

alias("listproj", "lsprj")

@app.cmd
@app.cmd_arg('text', type=str, nargs='+', help="The description of the task")
def add(calendar_name, text):
    text = " ".join(text)
    cal = caldav.vobject.iCalendar()
    todo = cal.add('vtodo')
    date = datetime.utcnow().replace(tzinfo=utc)
    todo.add('class').value = 'PUBLIC'
    todo.add('summary').value = text
    todo.add('created').value = date
    todo.add('dtstamp').value = date
    todo.add('last-modified').value = date
    # organizer = todo.add('organizer')
    # organizer.value = "mailto:%s" % ACCOUNT_EMAIL_ADDRESS
    # organizer.params["CN"] = [ACCOUNT_FULL_NAME]
    # todo.add('percent-complete').value = "0"
    # priority 0 is undefined priority
    todo.add('priority').value = "0"
    # todo.add('sequence').value = "0"
    todo.add('status').value = 'NEEDS-ACTION'
    todo.add('uid').value = uid = str(uuid.uuid4())
    try:
        task = caldav.Event(client, data=cal.serialize(), parent=client.get_calendar(calendar_name), id=uid)
        task.save()
    except Exception, e:
        print "Error saving event: %r" % e
    task_lookup = client.get_tasks(calendar_name)
    task_lookup[uid] = task
    print task_lookup.shortest(uid), task.format()

alias("add", "a")

@app.cmd
@app.cmd_arg('tasks', type=str, nargs='+', help="The description of the tasks (one per line)")
def addm(calendar_name, tasks):
    tasks = [task.strip() for task in " ".join(tasks).split("\n") if task.strip()]
    for task in tasks:
        add(calendar_name, [task])

@app.cmd
@app.cmd_arg('task_id', type=str, help="ID of the task to amend")
@app.cmd_arg('text', type=str, nargs='+', help="New summary text for the task")
def replace(calendar_name, task_id, text):
    text = " ".join(text)
    task = client.get_task(calendar_name, task_id)
    vtodo = task.instance.vtodo
    vtodo.summary.value = text
    task.save()
    task_lookup = client.get_tasks(calendar_name)
    print task_lookup.shortest(task_id), task.format()

@app.cmd
@app.cmd_arg('task_id', type=str, help="ID of the task to amend")
@app.cmd_arg('text', type=str, nargs='+', help="Extra text to append to the task")
def append(calendar_name, task_id, text):
    text = " ".join(text)
    task = client.get_task(calendar_name, task_id)
    vtodo = task.instance.vtodo
    vtodo.summary.value = vtodo.summary.value.rstrip(" ") + " " + text
    task.save()
    task_lookup = client.get_tasks(calendar_name)
    print task_lookup.shortest(task_id), task.format()

alias("append", "app")

@app.cmd
@app.cmd_arg('task_id', type=str, help="ID of the task to amend")
@app.cmd_arg('text', type=str, nargs='+', help="Extra text to prepend to the task")
def prepend(calendar_name, task_id, text):
    text = " ".join(text)
    task = client.get_task(calendar_name, task_id)
    vtodo = task.instance.vtodo
    vtodo.summary.value = text + " " + vtodo.summary.value.lstrip(" ")
    task.save()
    task_lookup = client.get_tasks(calendar_name)
    print task_lookup.shortest(task_id), task.format()

alias("prepend", "prep")

@app.cmd
@app.cmd_arg('task_id', type=str, help="ID of the task to delete")
def rm(calendar_name, task_id):
    task = client.get_task(calendar_name, task_id)
    task_lookup = client.get_tasks(calendar_name)
    print task_lookup.shortest(task_id), task.format()
    answer = ""
    while answer not in {"y", "n"}:
        answer = raw_input("delete (y/n)").lower()
    if answer == "y":
        task.delete()

alias("rm", "del")

@app.cmd
@app.cmd_arg('priority', type=str, help="Priority")
@app.cmd_arg('task_id', type=str, help="ID of the task to prioritize")
def pri(calendar_name, priority, task_id):
    task = client.get_task(calendar_name, task_id)
    vtodo = task.instance.vtodo
    priority = task.parse_priority(priority)
    if not hasattr(vtodo, "priority"):
        vtodo.add("priority").value = priority
    else:
        vtodo.priority.value = priority
    task.save()
    task_lookup = client.get_tasks(calendar_name)
    print task_lookup.shortest(task_id), task.format()

alias("pri", "p")

@app.cmd
@app.cmd_arg('task_ids', type=str, nargs='+', help="ID of the task(s) to deprioritize")
def depri(calendar_name, task_ids):
    task_lookup = client.get_tasks(calendar_name)
    for task_id in task_ids:
        task = client.get_task(calendar_name, task_id)
        vtodo = task.instance.vtodo
        # TODO: this doesn't seem to correspond to priority on Thunderbird??
        if not hasattr(vtodo, "priority"):
            vtodo.add("priority").value = "0"
        else:
            vtodo.priority.value = "0"
        task.save()
        print task_lookup.shortest(task_id), task.format()

alias("depri", "dp")

@app.cmd
@app.cmd_arg('task_ids', type=str, nargs='+', help="ID of the task(s) to mark as done")
def do(calendar_name, task_ids):
    task_lookup = client.get_tasks(calendar_name)
    for task_id in task_ids:
        task = client.get_task(calendar_name, task_id)
        vtodo = task.instance.vtodo
        if not hasattr(vtodo, "status"):
            vtodo.add("status").value = "COMPLETED"
        else:
            vtodo.status.value = "COMPLETED"
        if hasattr(vtodo, "percent_complete"):
            vtodo.percent_complete.value = "100"
        task.save()
        print task_lookup.shortest(task_id), task.format()

if __name__ == "__main__":
    app.run()



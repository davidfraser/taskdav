#!/usr/bin/env python

import config
cfg = config.get_config()

from datetime import datetime
import caldav
import re
import urllib2
import uuid
import short_id
import aaargh
import dateutil

utc = caldav.vobject.icalendar.utc

def get_object_urlname(davobject):
    """Returns the last component of the url path as the object's name"""
    name = davobject.url.path.rstrip("/")
    name = name if "/" not in name else name[name.rfind("/")+1:]
    return urllib2.unquote(name)

class TaskDAVClient(caldav.DAVClient):
    """Client that knows about tasks"""
    def __init__(self, url):
        caldav.DAVClient.__init__(self, url)
        # cache a principal we can use
        self.principal = caldav.Principal(self, url)
        self.calendar_lookup = {}
        self.calendar_tasks = {}

    def cache_calendars(self):
        self.calendar_lookup = {}
        calendars = self.principal.calendars()
        for calendar in calendars:
            name = calendar.name or get_object_urlname(calendar)
            # print (calendar.url.geturl(), name, calendar.id)
            self.calendar_lookup[name] = calendar

    def get_calendar(self, calendar_name):
        if not calendar_name in self.calendar_lookup:
            self.cache_calendars()
        return self.calendar_lookup[calendar_name]

    def cache_tasks(self, calendar_name):
        self.calendar_tasks[calendar_name] = tasks = short_id.prefix_dict()
        for task in self.get_calendar(calendar_name).events():
            task_id = task.id or (get_object_urlname(task).replace(".ics", ""))
            tasks[task_id] = task

    def get_tasks(self, calendar_name):
        if not calendar_name in self.calendar_tasks:
            self.cache_tasks(calendar_name)
        return self.calendar_tasks[calendar_name]

    def get_task(self, calendar_name, task_id):
        tasks = self.get_tasks(calendar_name)
        task = tasks.unique(task_id)
        if not task.instance:
            task.load()
        if not task.id:
            task.id = task.instance.vtodo.uid.value
        return task

url = cfg.get('server', 'url').replace("://", "://%s:%s@" % (cfg.get('server', 'username'), cfg.get('server', 'password'))) + "dav/%s/" % (cfg.get('server', 'username'),)
client = TaskDAVClient(url)

app = aaargh.App(description="A simple command-line tool for interacting with Tasks over CalDAV")

app.arg('-n', '--calendar-name', help="Name of the calendar to use", default="Tasks")

def alias(name, alias_name):
    """Adds an alias to the given command name"""
    # TODO: extend aaargh to handle this properly, so that it displays the aliases etc
    parser_map = app._parser._subparsers._group_actions[0]._name_parser_map
    parser_map[alias_name] = parser_map[name]

# priority map: A-D = 1-4 (high), none=0=5 (medium), E-H=6-9 (low)
PRIORITIES = [("A", 1), ("B", 2), ("C", 3), ("D", 4), ("", 5), ("", 0), ("E", 6), ("F", 7), ("G", 8), ("H", 9)]
PRIORITY_C2I = {pc: pi for pc, pi in PRIORITIES if pc}
PRIORITY_I2C = {pi: "(%s)" % pc if pc else "" for pc, pi in PRIORITIES}
PRIORITY_RE = re.compile(r'([A-Ha-h]|[A-Ha-h]-[A-Ha-h])')

def get_todo_attr_value(vtodo, attrname):
    return getattr(getattr(vtodo, attrname, None), "value", None)

def format_task(task):
    if not task.instance:
        task.load()
    vtodo = task.instance.vtodo
    gtav = lambda attrname: get_todo_attr_value(vtodo, attrname)
    priority = PRIORITY_I2C[int(gtav("priority") or "0")]
    return "%s%s %s" % (priority + " " if priority else "", gtav("summary"), gtav("status"))

__NOT_FOUND = object()

def attrs(obj, default, *attrs):
    """looks up a sequence of attributes in sequence, returning the default if any of them are not found"""
    for attr in attrs:
        obj = getattr(obj, attr, __NOT_FOUND)
        if obj is __NOT_FOUND:
            return default
    return obj

def task_attr(task, attrname, default=""):
    """returns the given task's attribute by looking up task.instance.vtodo.[attrname].value"""
    return attrs(task.instance, default, "vtodo", attrname, "value")

@app.cmd(name="list", help="Displays all incomplete tasks containing the given search terms (if any) either as ID prefix or summary text; a term like test- ending with a - is a negative search")
@app.cmd_arg('term', type=str, nargs='*', help="Search terms")
def list_(calendar_name, term):
    task_lookup = client.get_tasks(calendar_name)
    # TODO: make lookup by known ID not have to load all tasks
    term = [t.lower() for t in term]
    for task_id in sorted(task_lookup):
        task = client.get_task(calendar_name, task_id)
        if task_attr(task, "status") != "COMPLETED":
            search_text = task_attr(task, "summary").lower()
            if all(task.id.startswith(t) or (t[:-1] not in search_text if t.endswith('-') else t in search_text) for t in term):
                print task_lookup.shortest(task_id), task_id, format_task(task)

alias("list", "ls")

@app.cmd(help="Displays all tasks containing the given search terms (if any) either as ID prefix or summary text; a term like test- ending with a - is a negative search")
@app.cmd_arg('term', type=str, nargs='*', help="Search terms")
def listall(calendar_name, term):
    task_lookup = client.get_tasks(calendar_name)
    # TODO: make lookup by known ID not have to load all tasks
    term = [t.lower() for t in term]
    for task_id in sorted(task_lookup):
        task = client.get_task(calendar_name, task_id)
        search_text = task_attr(task, "summary").lower()
        if all(task.id.startswith(t) or (t[:-1] not in search_text if t.endswith('-') else t in search_text) for t in term):
            print task_lookup.shortest(task_id), task_id, format_task(task)

alias("listall", "lsa")

@app.cmd(help="Displays all incomplete tasks of the given (or any) priority containing the given search terms (if any) either as ID prefix or summary text; a term like test- ending with a - is a negative search")
@app.cmd_arg('priority', type=str, nargs='?', help="Priority")
@app.cmd_arg('term', type=str, nargs='*', help="Search terms")
def listpri(calendar_name, priority, term):
    if priority and not PRIORITY_RE.match(priority):
        term.insert(0, priority)
        priority = None
    if priority:
        priority = priority.upper()
        if "-" in priority:
            start_i, stop = PRIORITY_C2I[priority[0]], PRIORITY_C2I[priority[2]]
            priorities = {pi for pc, pi in PRIORITIES if start_i <= pi <= stop_i and pc}
        else:
            priorities = {PRIORITY_C2I[priority]}
    else:
        priorities = {pi for pc, pi in PRIORITIES if pc}
    task_lookup = client.get_tasks(calendar_name)
    term = [t.lower() for t in term]
    for task_id in sorted(task_lookup):
        task = client.get_task(calendar_name, task_id)
        if task_attr(task, "status") != "COMPLETED" and int(task_attr(task, "priority", "") or "0") in priorities:
            search_text = task_attr(task, "summary").lower()
            if all(task.id.startswith(t) or (t[:-1] not in search_text if t.endswith('-') else t in search_text) for t in term):
                print task_lookup.shortest(task_id), task_id, format_task(task)

alias("listpri", "lsp")

CONTEXT_RE = re.compile(r'(?:^|\s)(@\w*\b)')

@app.cmd(help="Lists all the task contexts that start with the @ sign in task summaries")
def listcon(calendar_name):
    task_lookup = client.get_tasks(calendar_name)
    contexts = set()
    for task_id in task_lookup:
        task = client.get_task(calendar_name, task_id)
        if task_attr(task, "status") != "COMPLETED":
            summary = task_attr(task, "summary")
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
        if task_attr(task, "status") != "COMPLETED":
            summary = task_attr(task, "summary")
            projects.update(PROJ_RE.findall(summary))
    for project in sorted(projects):
        print project

alias("listproj", "lsprj")

@app.cmd
@app.cmd_arg('task', type=str, nargs='+', help="The description of the task")
def add(calendar_name, task):
    task = " ".join(task)
    cal = caldav.vobject.iCalendar()
    todo = cal.add('vtodo')
    date = datetime.utcnow().replace(tzinfo=utc)
    todo.add('class').value = 'PUBLIC'
    todo.add('summary').value = task
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
    todo.add('uid').value = uid = str(uuid.uuid1())
    try:
        event = caldav.Event(client, data=cal.serialize(), parent=client.get_calendar(calendar_name), id=uid)
        event.save()
    except Exception, e:
        print "Error saving event: %r" % e
    print uid, format_task(event)

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
    print task_id, task.id, format_task(task)

@app.cmd
@app.cmd_arg('task_id', type=str, help="ID of the task to amend")
@app.cmd_arg('text', type=str, nargs='+', help="Extra text to append to the task")
def append(calendar_name, task_id, text):
    text = " ".join(text)
    task = client.get_task(calendar_name, task_id)
    vtodo = task.instance.vtodo
    vtodo.summary.value = vtodo.summary.value.rstrip(" ") + " " + text
    task.save()
    print task_id, task.id, format_task(task)

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
    print task_id, task.id, format_task(task)

alias("prepend", "prep")

@app.cmd
@app.cmd_arg('task_id', type=str, help="ID of the task to delete")
def rm(calendar_name, task_id):
    task = client.get_task(calendar_name, task_id)
    print task_id, task.id, format_task(task)
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
    priority = str(PRIORITY_C2I[priority])
    if not hasattr(vtodo, "priority"):
        vtodo.add("priority").value = priority
    else:
        vtodo.priority.value = priority
    task.save()
    print task_id, task.id, format_task(task)

alias("pri", "p")

@app.cmd
@app.cmd_arg('task_ids', type=str, nargs='+', help="ID of the task(s) to deprioritize")
def depri(calendar_name, task_ids):
    for task_id in task_ids:
        task = client.get_task(calendar_name, task_id)
        vtodo = task.instance.vtodo
        # TODO: this doesn't seem to correspond to priority on Thunderbird??
        if not hasattr(vtodo, "priority"):
            vtodo.add("priority").value = "0"
        else:
            vtodo.priority.value = "0"
        task.save()
        print task_id, task.id, format_task(task)

alias("depri", "dp")

@app.cmd
@app.cmd_arg('task_ids', type=str, nargs='+', help="ID of the task(s) to mark as done")
def do(calendar_name, task_ids):
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
        print task_id, task.id, format_task(task)

if __name__ == "__main__":
    app.run()


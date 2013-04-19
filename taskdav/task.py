#!/usr/bin/env python

import config
cfg = config.get_config()

from datetime import datetime
import caldav
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

def get_todo_attr_value(vtodo, attrname):
    return getattr(getattr(vtodo, attrname, None), "value", None)

def format_task(task):
    if not task.instance:
        task.load()
    vtodo = task.instance.vtodo
    gtav = lambda attrname: get_todo_attr_value(vtodo, attrname)
    return "%s %s %s" % ( gtav("status"), gtav("summary"), gtav("priority"))

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
    for task_id in sorted(task_lookup):
        task = client.get_task(calendar_name, task_id)
        if task_attr(task, "status") != "COMPLETED":
            search_text = task_attr(task, "summary")
            if all(task.id.startswith(t) or (t[:-1] not in search_text if t.endswith('-') else t in search_text) for t in term):
                print task_lookup.shortest(task_id), task_id, format_task(task)

alias("list", "ls")

@app.cmd(help="Displays all tasks containing the given search terms (if any) either as ID prefix or summary text; a term like test- ending with a - is a negative search")
@app.cmd_arg('term', type=str, nargs='*', help="Search terms")
def listall(calendar_name, term):
    task_lookup = client.get_tasks(calendar_name)
    # TODO: make lookup by known ID not have to load all tasks
    for task_id in sorted(task_lookup):
        task = client.get_task(calendar_name, task_id)
        search_text = task_attr(task, "summary")
        if all(task.id.startswith(t) or (t[:-1] not in search_text if t.endswith('-') else t in search_text) for t in term):
            print task_lookup.shortest(task_id), task_id, format_task(task)

alias("listall", "lsa")

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
    # todo.add('priority').value = "5"
    # todo.add('sequence').value = "0"
    todo.add('status').value = 'NEEDS-ACTION'
    todo.add('uid').value = uid = str(uuid.uuid1())
    try:
        event = caldav.Event(client, data=cal.serialize(), parent=client.get_calendar(calendar_name), id=uid)
        event.save()
    except Exception, e:
        print "Error saving event: %r" % e

alias("add", "a")

@app.cmd
@app.cmd_arg('tasks', type=str, nargs='+', help="The description of the tasks (one per line)")
def addm(calendar_name, tasks):
    tasks = [task.strip() for task in " ".join(tasks).split("\n") if task.strip()]
    for task in tasks:
        add(calendar_name, [task])

@app.cmd
@app.cmd_arg('task_id', type=str, help="ID of the task to add to")
@app.cmd_arg('text', type=str, nargs='+', help="Extra text to add to the task")
def append(calendar_name, task_id, text):
    text = " ".join(text)
    task = client.get_task(calendar_name, task_id)
    vtodo = task.instance.vtodo
    vtodo.summary.value = vtodo.summary.value.rstrip(" ") + " " + text
    task.save()
    print task_id, task.id, format_task(task)

alias("append", "app")

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
@app.cmd_arg('task_ids', type=str, nargs='+', help="ID of the task(s) to deprioritize")
def depri(calendar_name, task_ids):
    for task_id in task_ids:
        task = client.get_task(calendar_name, task_id)
        vtodo = task.instance.vtodo
        # TODO: this doesn't seem to correspond to priority on Thunderbird??
        if not hasattr(vtodo, "priority"):
            vtodo.add("priority").value = "5"
        else:
            vtodo.priority.value = "5"
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


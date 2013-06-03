#!/usr/bin/env python

"""todo.txt command-line compatibility - implements many commands from todo.txt"""

from taskdav.task import Task, TaskDAVClient
from taskdav import config
from datetime import datetime
import caldav
import re
import aaargh
import colorama

cfg = config.get_config()
url = cfg.get('server', 'url').replace("://", "://%s:%s@" % (cfg.get('server', 'username'), cfg.get('server', 'password'))) + "dav/%s/" % (cfg.get('server', 'username'),)
client = TaskDAVClient(url)

utc = caldav.vobject.icalendar.utc

app = aaargh.App(description="A simple command-line tool for interacting with Tasks over CalDAV")

app.arg('-n', '--calendar-name', help="Name of the calendar to use", default="Tasks")
app.arg('-c', '--color', dest='color', action="store_true", help="Color output mode", default=True)
app.arg('-p', '--no-color', dest='color', action="store_false", help="Plain output mode (disable color)")

def setup_color(enabled):
    """Enables or disables color output"""
    if enabled:
        colorama.init()
    else:
        colorama.init(strip=True, convert=False)

PRIORITY_COLOR_MAP = {
        1: colorama.Fore.CYAN,
        2: colorama.Fore.GREEN,
        3: colorama.Fore.YELLOW,
        8: colorama.Style.BRIGHT, # Waiting
    }
    
def output_task(task_lookup, task):
    print PRIORITY_COLOR_MAP.get(task.priority, "") + task_lookup.shortest(task.id), task.format() + colorama.Style.RESET_ALL

def alias(name, alias_name):
    """Adds an alias to the given command name"""
    # TODO: if https://github.com/wbolster/aaargh/pull/4 is accepted, replace this with alias= arguments
    parser_map = app._parser._subparsers._group_actions[0]._name_parser_map
    parser_map[alias_name] = parser_map[name]

STATUS_KEY = {"NEEDS-ACTION": 0, "IN-PROCESS": 1, "COMPLETED": 2, "CANCELLED": 3}

def sorted_tasks(task_lookup):
    """returns the given tasks sorted by priority, then status, then summary"""
    return sorted(task_lookup, key=lambda t: (task_lookup[t].priority or 5, STATUS_KEY.get(task_lookup[t].status.upper(), task_lookup[t].status), task_lookup[t].summary))

@app.cmd(name="list", help="Displays all incomplete tasks containing the given search terms (if any) either as ID prefix or summary text; a term like test- ending with a - is a negative search")
@app.cmd_arg('term', type=str, nargs='*', help="Search terms")
def list_(calendar_name, term, color):
    setup_color(color)
    calendar = client.get_calendar(calendar_name)
    task_lookup = calendar.get_tasks()
    # TODO: make lookup by known ID not have to load all tasks
    term = [t.lower() for t in term]
    for task_id in sorted_tasks(task_lookup):
        task = calendar.get_task(task_id)
        if task.status != "COMPLETED":
            search_text = task.summary.lower()
            if all(task.id.startswith(t) or (t[:-1] not in search_text if t.endswith('-') else t in search_text) for t in term):
                output_task(task_lookup, task)

alias("list", "ls")

@app.cmd(help="Displays all tasks containing the given search terms (if any) either as ID prefix or summary text; a term like test- ending with a - is a negative search")
@app.cmd_arg('term', type=str, nargs='*', help="Search terms")
def listall(calendar_name, term, color):
    setup_color(color)
    calendar = client.get_calendar(calendar_name)
    task_lookup = calendar.get_tasks()
    # TODO: make lookup by known ID not have to load all tasks
    term = [t.lower() for t in term]
    for task_id in sorted_tasks(task_lookup):
        task = calendar.get_task(task_id)
        search_text = task.summary.lower()
        if all(task.id.startswith(t) or (t[:-1] not in search_text if t.endswith('-') else t in search_text) for t in term):
            output_task(task_lookup, task)

alias("listall", "lsa")

@app.cmd(help="Reports on the number of open and done tasks")
def report(calendar_name, color):
    setup_color(color)
    date = datetime.utcnow().replace(tzinfo=utc)
    calendar = client.get_calendar(calendar_name)
    task_lookup = calendar.get_tasks()
    task_status_count = {}
    for task_id in task_lookup:
        task = calendar.get_task(task_id)
        status = task.status
        task_status_count[status] = task_status_count.get(status, 0) + 1
    print date
    for status in sorted(task_status_count):
        print status, task_status_count[status]

@app.cmd(help="Displays all incomplete tasks of the given (or any) priority containing the given search terms (if any) either as ID prefix or summary text; a term like test- ending with a - is a negative search")
@app.cmd_arg('priority', type=str, nargs='?', help="Priority")
@app.cmd_arg('term', type=str, nargs='*', help="Search terms")
def listpri(calendar_name, priority, term, color):
    setup_color(color)
    try:
        priorities = Task.parse_priority_range(priority)
    except KeyError:
        # Assume this wasn't really a priority
        term.insert(0, priority)
        priorities = Task.ALL_PRIORITIES
    calendar = client.get_calendar(calendar_name)
    task_lookup = calendar.get_tasks()
    term = [t.lower() for t in term]
    for task_id in sorted_tasks(task_lookup):
        task = calendar.get_task(task_id)
        if task.status != "COMPLETED" and task.priority in priorities:
            search_text = task.summary.lower()
            if all(task.id.startswith(t) or (t[:-1] not in search_text if t.endswith('-') else t in search_text) for t in term):
                output_task(task_lookup, task)

alias("listpri", "lsp")

CONTEXT_RE = re.compile(r'(?:^|\s)(@\w*\b)')

@app.cmd(help="Lists all the task contexts that start with the @ sign in task summaries")
def listcon(calendar_name, color):
    setup_color(color)
    calendar = client.get_calendar(calendar_name)
    task_lookup = calendar.get_tasks()
    contexts = set()
    for task_id in task_lookup:
        task = calendar.get_task(task_id)
        if task.status != "COMPLETED":
            contexts.update(CONTEXT_RE.findall(task.summary))
    for context in sorted(contexts):
        print context

alias("listcon", "lsc")

PROJ_RE = re.compile(r'(?:^|\s)(\+\w*\b)')

@app.cmd(help="Lists all the task projects that start with the + sign in task summaries")
def listproj(calendar_name, color):
    setup_color(color)
    calendar = client.get_calendar(calendar_name)
    task_lookup = calendar.get_tasks()
    projects = set()
    for task_id in task_lookup:
        task = calendar.get_task(task_id)
        if task.status != "COMPLETED":
            projects.update(PROJ_RE.findall(task.summary))
    for project in sorted(projects):
        print project

alias("listproj", "lsprj")

PRIORITY_PREFIX_RE = re.compile('^[(]([A-FHWa-fhw])[)]\s+')

@app.cmd
@app.cmd_arg('text', type=str, nargs='+', help="The description of the task")
def add(calendar_name, text, color):
    setup_color(color)
    text = " ".join(text)
    prefix_match = PRIORITY_PREFIX_RE.match(text)
    if prefix_match:
        priority, text = Task.parse_priority(prefix_match.group(1)), text[prefix_match.end():]
    else:
        priority = None
    calendar = client.get_calendar(calendar_name)
    try:
        task = Task.new_task(client, parent=calendar, summary=text)
        if priority is not None:
            task.priority = priority
        task.save()
    except Exception, e:
        print "Error saving event: %r" % e
        return
    task_lookup = calendar.get_tasks()
    task_lookup[task.id] = task
    output_task(task_lookup, task)

alias("add", "a")

@app.cmd
@app.cmd_arg('tasks', type=str, nargs='+', help="The description of the tasks (one per line)")
def addm(calendar_name, tasks, color):
    setup_color(color)
    tasks = [task.strip() for task in " ".join(tasks).split("\n") if task.strip()]
    for task in tasks:
        add(calendar_name, [task], color)

@app.cmd
@app.cmd_arg('task_id', type=str, help="ID of the task to amend")
@app.cmd_arg('text', type=str, nargs='+', help="New summary text for the task")
def replace(calendar_name, task_id, text, color):
    setup_color(color)
    text = " ".join(text)
    calendar = client.get_calendar(calendar_name)
    task = calendar.get_task(task_id)
    task.summary = text
    task.save()
    task_lookup = calendar.get_tasks()
    output_task(task_lookup, task)

@app.cmd
@app.cmd_arg('task_id', type=str, help="ID of the task to amend")
@app.cmd_arg('text', type=str, nargs='+', help="Extra text to append to the task")
def append(calendar_name, task_id, text, color):
    setup_color(color)
    text = " ".join(text)
    calendar = client.get_calendar(calendar_name)
    task = calendar.get_task(task_id)
    task.summary = task.summary.rstrip(" ") + " " + text
    task.save()
    task_lookup = calendar.get_tasks()
    output_task(task_lookup, task)

alias("append", "app")

@app.cmd
@app.cmd_arg('task_id', type=str, help="ID of the task to amend")
@app.cmd_arg('text', type=str, nargs='+', help="Extra text to prepend to the task")
def prepend(calendar_name, task_id, text, color):
    setup_color(color)
    text = " ".join(text)
    calendar = client.get_calendar(calendar_name)
    task = calendar.get_task(task_id)
    task.summary = text + " " + task.summary.lstrip(" ")
    task.save()
    task_lookup = calendar.get_tasks()
    output_task(task_lookup, task)

alias("prepend", "prep")

@app.cmd
@app.cmd_arg('task_id', type=str, nargs='+', help="ID of the task to delete")
@app.cmd_arg('-y', action='store_false', dest='prompt', default=True, help="Don't prompt before deletion")
def rm(calendar_name, task_id, prompt, color):
    setup_color(color)
    calendar = client.get_calendar(calendar_name)
    task_lookup = calendar.get_tasks()
    for tid in task_id:
        task = calendar.get_task(tid)
        output_task(task_lookup, task)
        answer = "y"
        if prompt:
            answer = ""
            while answer not in {"y", "n"}:
                answer = raw_input("delete (y/n)").lower()
        if answer == "y":
            task.delete()
            print colorama.Fore.RED + "deleted" + colorama.Style.RESET_ALL

alias("rm", "del")

@app.cmd
@app.cmd_arg('task_id', type=str, help="ID of the task to prioritize")
@app.cmd_arg('priority', type=str, help="Priority")
def pri(calendar_name, task_id, priority, color):
    setup_color(color)
    calendar = client.get_calendar(calendar_name)
    task = calendar.get_task(task_id)
    task.priority = task.parse_priority(priority)
    task.save()
    task_lookup = calendar.get_tasks()
    output_task(task_lookup, task)

alias("pri", "p")

@app.cmd
@app.cmd_arg('task_ids', type=str, nargs='+', help="ID of the task(s) to deprioritize")
def depri(calendar_name, task_ids, color):
    setup_color(color)
    calendar = client.get_calendar(calendar_name)
    task_lookup = calendar.get_tasks()
    for task_id in task_ids:
        task = calendar.get_task(task_id)
        task.priority = 0
        task.save()
        output_task(task_lookup, task)

alias("depri", "dp")

@app.cmd
@app.cmd_arg('task_ids', type=str, nargs='+', help="ID of the task(s) to mark as done")
def do(calendar_name, task_ids, color):
    setup_color(color)
    calendar = client.get_calendar(calendar_name)
    task_lookup = calendar.get_tasks()
    for task_id in task_ids:
        task = calendar.get_task(task_id)
        task.status = "COMPLETED"
        task.todo_setattr("percent_complete", "100")
        task.save()
        output_task(task_lookup, task)

if __name__ == "__main__":
    app.run()



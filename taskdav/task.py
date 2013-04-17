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
        self.cache_calendars()

    def cache_calendars(self):
        self.calendar_lookup = {}
        calendars = self.principal.calendars()
        for calendar in calendars:
            name = calendar.name or get_object_urlname(calendar)
            # print (calendar.url.geturl(), name, calendar.id)
            self.calendar_lookup[name] = calendar

    def get_calendar(self, calendar_name):
        return self.calendar_lookup[calendar_name]

    def cache_tasks(self, calendar_name):
        self.calendar_tasks[calendar_name] = tasks = short_id.prefix_dict()
        for task in self.get_calendar(calendar_name).events():
            task_id = task.id or (get_object_urlname(task).replace(".ics", ""))
            tasks[task_id] = task

    def get_tasks(self, calendar_name):
        self.cache_tasks(calendar_name)
        return self.calendar_tasks[calendar_name]

url = cfg.get('server', 'url').replace("://", "://%s:%s@" % (cfg.get('server', 'username'), cfg.get('server', 'password'))) + "dav/%s/" % (cfg.get('server', 'username'),)
client = TaskDAVClient(url)

app = aaargh.App(description="A simple command-line tool for interacting with Tasks over CalDAV")

app.arg('-n', '--calendar-name', help="Name of the calendar to use", default="Tasks")

@app.cmd(name="list", help="List tasks")
def list_(calendar_name):
    task_lookup = client.get_tasks(calendar_name)
    for task_id in sorted(task_lookup):
        task = task_lookup[task_id]
        task.load()
        # task.instance.prettyPrint()
        vtodo = task.instance.vtodo
        print task_lookup.shortest(task_id), task_id, vtodo.status.value, vtodo.summary.value, vtodo.priority.value

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
    todo.add('status').value = 'NEEDS-ACTION'
    todo.add('uid').value = uid = str(uuid.uuid1())

    try:
        event = caldav.Event(client, data=cal.serialize(), parent=client.get_calendar(calendar_name), id=uid)
        event.save()
    except Exception, e:
        print "Error saving event: %r" % e

if __name__ == "__main__":
    app.run()


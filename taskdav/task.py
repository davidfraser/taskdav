#!/usr/bin/env python

import config
cfg = config.get_config()

from datetime import datetime
import caldav
import urllib2
import short_id

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

task_lookup = client.get_tasks("Tasks")
for task_id in sorted(task_lookup):
    task = task_lookup[task_id]
    task.load()
    # task.instance.prettyPrint()
    vtodo = task.instance.vtodo
    print task_lookup.shortest(task_id), task_id, vtodo.status.value, vtodo.summary.value, vtodo.priority.value


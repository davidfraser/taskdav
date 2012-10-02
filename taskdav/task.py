#!/usr/bin/env python

import config
cfg = config.get_config()

from datetime import datetime
import caldav
import urllib2
import short_id

url = cfg.get('server', 'url').replace("://", "://%s:%s@" % (cfg.get('server', 'username'), cfg.get('server', 'password'))) + "dav/%s/" % (cfg.get('server', 'username'),)

client = caldav.DAVClient(url)
principal = caldav.Principal(client, url)
calendars = principal.calendars()

calendar_lookup = {}

def get_object_urlname(davobject):
    """Returns the last component of the url path as the object's name"""
    name = davobject.url.path.rstrip("/")
    name = name if "/" not in name else name[name.rfind("/")+1:]
    return urllib2.unquote(name)

for calendar in calendars:
    name = calendar.name or get_object_urlname(calendar)
    # print (calendar.url.geturl(), name, calendar.id)
    calendar_lookup[name] = calendar

tasks_calendar = calendar_lookup["Tasks"]

tasks = tasks_calendar.events()
task_lookup = short_id.prefix_dict()

for task in tasks:
    task_id = task.id or (get_object_urlname(task).replace(".ics", ""))
    task_lookup[task_id] = task

for task_id in sorted(task_lookup):
    task = task_lookup[task_id]
    task.load()
    # task.instance.prettyPrint()
    vtodo = task.instance.vtodo
    print task_lookup.shortest(task_id), task_id, vtodo.status.value, vtodo.summary.value, vtodo.priority.value


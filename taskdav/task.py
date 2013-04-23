#!/usr/bin/env python

import caldav
import urllib2
import short_id

def get_object_urlname(davobject):
    """Returns the last component of the url path as the object's name"""
    name = davobject.url.path.rstrip("/")
    name = name if "/" not in name else name[name.rfind("/")+1:]
    return urllib2.unquote(name)

class Task(caldav.Event):
    def todo_attr(self, attr_name, default=""):
        """Returns the attribute from self.instance.vtodo with the given name's value, or default if not present"""
        if not self.instance:
            self.load()
        vtodo = self.instance.vtodo
        obj = getattr(vtodo, attr_name, None)
        return obj.value if obj is not None else default

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
            # TODO: just use task.url once patch accepted
            url = task.url.geturl() if task.url is not None else None
            tasks[task_id] = task = Task(task.client, url=url, data=task.data, parent=task.parent, id=task.id)

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


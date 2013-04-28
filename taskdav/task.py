#!/usr/bin/env python

import caldav
import re
import urllib2
import short_id

def get_object_urlname(davobject):
    """Returns the last component of the url path as the object's name"""
    name = davobject.url.path.rstrip("/")
    name = name if "/" not in name else name[name.rfind("/")+1:]
    return urllib2.unquote(name)

class Task(caldav.Event):
    # priority map: A-D = 1-4 (high), none=0=5 (medium), E-H=6-9 (low)
    PRIORITIES = [("A", 1), ("B", 2), ("C", 3), ("D", 4), ("", 5), ("", 0), ("E", 6), ("F", 7), ("G", 8), ("H", 9)]
    PRIORITY_C2I = {pc: pi for pc, pi in PRIORITIES if pc}
    PRIORITY_I2C = {pi: "(%s)" % pc if pc else "" for pc, pi in PRIORITIES}
    PRIORITY_RE = re.compile(r'([A-Ha-h]|[A-Ha-h]-[A-Ha-h])')
    ALL_PRIORITIES = {pi for pc, pi in PRIORITIES if pc}

    @classmethod
    def parse_priority_range(cls, priority_str):
        """Parses the given priority_str which can be either a single priority `C` or a range `B-E`, and return a set of caldav priority values"""
        if priority_str:
            if not cls.PRIORITY_RE.match(priority_str):
                raise ValueError("Priority range expression is not valid: %s" % priority_str)
            priority_str = priority_str.upper()
            if "-" in priority_str:
                start_i, stop_i = cls.PRIORITY_C2I[priority_str[0]], cls.PRIORITY_C2I[priority_str[2]]
                return {pi for pc, pi in cls.PRIORITIES if start_i <= pi <= stop_i and pc}
            else:
                return {cls.PRIORITY_C2I[priority_str]}
        else:
            return cls.ALL_PRIORITIES

    @classmethod
    def parse_priority(cls, priority_str):
        """Parses the given priority_str which must be a single priority `C`, and return a caldav priority value"""
        if priority_str:
            priority_str = priority_str.upper()
            return cls.PRIORITY_C2I[priority_str]
        else:
            return None

    def todo_getattr(self, attr_name, default=""):
        """Returns the attribute from self.instance.vtodo with the given name's value, or default if not present"""
        if not self.instance:
            self.load()
        vtodo = self.instance.vtodo
        obj = getattr(vtodo, attr_name, None)
        return obj.value if obj is not None else default

    def format(self):
        """Formats a task for output"""
        if not self.instance:
            self.load()
        priority = self.PRIORITY_I2C[int(self.todo_getattr("priority") or "0")]
        status = self.todo_getattr("status")
        status_str = ("x " if status == "COMPLETED" else "") + (priority + " " if priority else "")
        return "%s%s %s" % (status_str, self.todo_getattr("summary"), self.todo_getattr("status"))

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


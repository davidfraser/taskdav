#!/usr/bin/env python

import caldav
import re
import uuid
import urlparse
import urllib2
import short_id
from datetime import datetime
from lxml import etree
from caldav.elements import base, cdav, dav
from caldav.lib import error, vcal, url
from caldav.lib.namespace import ns

utc = caldav.vobject.icalendar.utc

def get_object_urlname(davobject):
    """Returns the last component of the url path as the object's name"""
    name = davobject.url.path.rstrip("/")
    name = name if "/" not in name else name[name.rfind("/")+1:]
    return urllib2.unquote(name)

class Task(caldav.Event):
    # priority map: A-D = 1-4 (high), none=0=5 (medium), E-H=6-9 (low) except G has been temporarily replaced with W for delegated tasks
    # TODO: find another way to do task delegation
    PRIORITIES = [("A", 1), ("B", 2), ("C", 3), ("D", 4), ("", 5), ("", 0), ("E", 6), ("F", 7), ("W", 8), ("H", 9)]
    PRIORITY_C2I = {pc: pi for pc, pi in PRIORITIES if pc}
    PRIORITY_I2C = {pi: "(%s)" % pc if pc else "" for pc, pi in PRIORITIES}
    PRIORITY_RE = re.compile(r'([A-FHWa-fhw]|[A-FHWa-fhw]-[A-FHWa-fhw])')
    ALL_PRIORITIES = {pi for pc, pi in PRIORITIES if pc}

    def load(self):
        """
        Load the task from the caldav server.
        """
        r = self.client.request(self.url.path)
        self.data = vcal.fix(r.raw)
        return self

    @classmethod
    def new_task(cls, client, parent, summary, **attrs):
        """constructs a new task on the given client and parent calendar with the given summary and other attrs, defaulting to sensible defaults otherwise"""
        cal = caldav.vobject.iCalendar()
        todo = cal.add('vtodo')
        default_date = datetime.utcnow().replace(tzinfo=utc)
        todo.add('class').value = attrs.get('class', 'PUBLIC')
        todo.add('summary').value = summary
        todo.add('created').value = attrs.get('created', default_date)
        todo.add('dtstamp').value = attrs.get('dtstamp', default_date)
        todo.add('last-modified').value = attrs.get('last-modified', default_date)
        # organizer = todo.add('organizer')
        # organizer.value = "mailto:%s" % ACCOUNT_EMAIL_ADDRESS
        # organizer.params["CN"] = [ACCOUNT_FULL_NAME]
        # todo.add('percent-complete').value = "0"
        # priority 0 is undefined priority
        todo.add('priority').value = "0"
        # todo.add('sequence').value = "0"
        todo.add('status').value = 'NEEDS-ACTION'
        todo.add('uid').value = uid = attrs.get('uid', str(uuid.uuid4()))
        return cls(client, data=cal.serialize(), parent=parent, id=uid)

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

    def todo_setattr(self, attr_name, value):
        """sets the attribute from self.instance.vtodo to the given value"""
        if not self.instance:
            self.load()
        vtodo = self.instance.vtodo
        if not hasattr(vtodo, attr_name):
            vtodo.add(attr_name).value = value
        else:
            getattr(vtodo, attr_name).value = value

    @property
    def status(self):
        """Returns the current status"""
        return self.todo_getattr("status", None)

    @status.setter
    def status(self, value):
        self.todo_setattr("status", value)

    @property
    def priority(self):
        """Returns the current priority as an integer"""
        return int(self.todo_getattr("priority", "0"))

    @priority.setter
    def priority(self, value):
        if not isinstance(value, int):
            value = int(value or "0")
        self.todo_setattr("priority", str(value))

    @property
    def summary(self):
        """Returns the current summary"""
        return self.todo_getattr("summary", "")

    @summary.setter
    def summary(self, value):
        self.todo_setattr("summary", value)

    def format(self):
        """Formats a task for output"""
        if not self.instance:
            self.load()
        priority = self.PRIORITY_I2C[self.priority]
        status = self.status
        status_str = ("x " if status == "COMPLETED" else "") + (priority + " " if priority else "")
        return "%s%s %s" % (status_str, self.summary, status)

class TaskList(caldav.Calendar):
    event_cls = Task
    _tasks = None

    def tasks(self):
        """
        Search tasks in the calendar

        Returns:
         * [Task(), ...]
        """
        matches = []

        # build the request
        getetag = dav.GetEtag()
        data = cdav.CalendarData()
        prop = dav.Prop() + [getetag, data]

        vevent = cdav.CompFilter("VTODO")
        vcal = cdav.CompFilter("VCALENDAR") + vevent
        filter = cdav.Filter() + vcal

        root = cdav.CalendarQuery() + [prop, filter]

        q = etree.tostring(root.xmlelement(), encoding="utf-8",
                           xml_declaration=True)
        response = self.client.report(self.url.path, q, 1)
        for r in response.tree.findall(".//" + dav.Response.tag):
            status = r.find(".//" + dav.Status.tag)
            if status.text.endswith("200 OK"):
                href = urlparse.urlparse(r.find(dav.Href.tag).text)
                href = url.canonicalize(href, self)
                data = r.find(".//" + cdav.CalendarData.tag).text
                etag = r.find(".//" + dav.GetEtag.tag).text
                e = self.event_cls(self.client, url=href, data=data, parent=self, etag=etag)
                matches.append(e)
            else:
                raise error.ReportError(response.raw)

        return matches

    def load_tasks(self):
        """loads all tasks in this TaskList into a lookup by id"""
        self._tasks = tasks = short_id.prefix_dict()
        for task in self.tasks():
            task_id = task.id or (get_object_urlname(task).replace(".ics", ""))
            tasks[task_id] = task

    def get_tasks(self):
        """returns a lookup making id to task for all tasks in this TaskList"""
        if self._tasks is None:
            self.load_tasks()
        return self._tasks

    def get_task(self, task_id):
        """returns a task by id, ensuring it is loaded"""
        tasks = self.get_tasks()
        task = tasks.unique(task_id)
        if not task.instance:
            task.load()
        if not task.id:
            task.id = task.instance.vtodo.uid.value
        return task

class TaskPrincipal(caldav.Principal):
    calendar_cls = TaskList

class TaskDAVClient(caldav.DAVClient):
    """Client that knows about tasks"""
    def __init__(self, url):
        caldav.DAVClient.__init__(self, url)
        # cache a principal we can use
        self.principal = TaskPrincipal(self, url)
        self.calendar_lookup = {}

    def load_calendars(self):
        self.calendar_lookup = {}
        calendars = self.principal.calendars()
        for calendar in calendars:
            name = calendar.name or get_object_urlname(calendar)
            # print (calendar.url.geturl(), name, calendar.id)
            self.calendar_lookup[name] = calendar

    def get_calendar(self, calendar_name):
        if not calendar_name in self.calendar_lookup:
            self.load_calendars()
        return self.calendar_lookup[calendar_name]

    def load_tasks(self, calendar_name):
        self.get_calendar(calendar_name).load_tasks()

    def get_tasks(self, calendar_name):
        return self.get_calendar(calendar_name).get_tasks()

    def get_task(self, calendar_name, task_id):
        return self.get_calendar(calendar_name).get_task(task_id)


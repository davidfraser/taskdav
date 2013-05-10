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
    def new_task(cls, client, parent, summary, **attrs):
        """constructs a new task on the given client and parent calendar with the given summary and other attrs, defaulting to sensible defaults otherwise"""
        cal = caldav.vobject.iCalendar()
        todo = cal.add('vtodo')
        default_date = datetime.utcnow().replace(tzinfo=utc)
        todo.add('class').value = attrs.get('class', 'PUBLIC')
        todo.add('summary').value = summary
        todo.add('created').value = attrs.get('created', date)
        todo.add('dtstamp').value = attrs.get('dtstamp', date)
        todo.add('last-modified').value = attrs.get('last-modified', date)
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
            vtodo.attr_name.value = value

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
        self.todo_setattr("priority", value)

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
        priority = self.PRIORITY_I2C[int(self.todo_getattr("priority") or "0")]
        status = self.todo_getattr("status")
        status_str = ("x " if status == "COMPLETED" else "") + (priority + " " if priority else "")
        return "%s%s %s" % (status_str, self.todo_getattr("summary"), self.todo_getattr("status"))

class TaskList(caldav.Calendar):
    event_cls = Task
    def __init__(self, client, url=None, parent=None, name=None, id=None):
        caldav.Calendar.__init__(self, client, url, parent, name, id)
        self.tasks = None

    def load_tasks(self):
        self.tasks = tasks = short_id.prefix_dict()
        for task in self.events():
            task_id = task.id or (get_object_urlname(task).replace(".ics", ""))
            tasks[task_id] = task

    def get_tasks(self):
        if self.tasks is None:
            self.load_tasks()
        return self.tasks

    def get_task(self, task_id):
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
        self.calendar_tasks = {}

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


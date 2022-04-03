import time
from threading import Lock, Thread
from random import randint

from rpyc import Service, ThreadedServer
from rpyc.utils.helpers import classpartial
from rpyc.utils.server import Server

resource_lock = Lock()
t_cs = 10
T_LOWER = 10


class Resource(Thread):
    def __init__(self, port: int, t_cs: int = 5):
        super().__init__()
        self.port = port
        self.t_cs = t_cs

    def run(self):
        service = classpartial(ResourceService, self)
        ThreadedServer(service, port=self.port).start()


class ResourceService(Service):
    def __init__(self, resource: Resource):
        self.resource = resource

    def exposed_set_time(self, t):
        if t < T_LOWER:
            raise Exception(f"time must be greater or eqal to {T_LOWER}")
        self.resource.t_cs = t

    def exposed_use(self):
        if resource_lock.locked():
            raise Exception("Resource already in use")

        with resource_lock:
            time.sleep(randint(T_LOWER, t_cs))

import logging
from threading import Lock, Thread, Event
from random import randint

from rpyc import Service, ThreadedServer
from rpyc.utils.helpers import classpartial

T_LOWER = 10

logger = logging.getLogger(__name__)


class Resource(Thread):
    def __init__(self, port: int):
        super().__init__()
        self.port = port
        self._time = 10
        self.lock = Lock()

    @property
    def time(self) -> int:
        return self._time

    def set_time(self, t):
        if t < T_LOWER:
            raise Exception(f"Time must be greater or equal to {T_LOWER}.")

        self._time = t

    def run(self):
        logger.info(f"Resource is starting a server with port {self.port}")
        service = classpartial(ResourceService, self)
        ThreadedServer(service, port=self.port).start()


class ResourceService(Service):
    def __init__(self, resource: Resource):
        self.resource = resource

    def exposed_use(self):
        if self.resource.lock.locked():
            raise Exception("Resource already in use")

        with self.resource.lock:
            Event().wait(randint(T_LOWER, self.resource.time))

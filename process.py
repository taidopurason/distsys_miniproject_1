from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass, asdict
from enum import Enum
from threading import Lock, Thread
from random import randint

from typing import Optional, List

import rpyc
from rpyc import Service
from rpyc.utils.helpers import classpartial
from rpyc.utils.server import ThreadedServer

logger = logging.getLogger(__name__)


class State(str, Enum):
    HELD = "HELD"
    WANTED = "WANTED"
    DO_NOT_WANT = "DO-NOT-WANT"


class MessageType(str, Enum):
    REQUEST = "REQUEST"
    REPLY = "REPLY"


T_LOWER = 5


class LamportClock:
    def __init__(self, time: int = 0):
        self.time = time
        self.lock = Lock()

    def increment(self, new_time: int = 0):
        with self.lock:
            self.time = max(new_time, self.time) + 1
            return self.time


class ResponseQueue:
    def __init__(self):
        self.queue = set()
        self.lock = Lock()

    def add(self, item):
        with self.lock:
            self.queue.add(item)

    def pop(self):
        with self.lock:
            return self.queue.pop()

    def __len__(self):
        with self.lock:
            return len(self.queue)


class Requests:
    def __init__(self):
        self.requests = set()
        self.lock = Lock()

    def add(self, item):
        with self.lock:
            self.requests.add(item)

    def remove(self, item):
        with self.lock:
            self.requests.remove(item)

    def is_waiting(self):
        with self.lock:
            return len(self.requests) > 0


class ProcessService(Service):
    def __init__(self, process: Process):
        self.process = process

    def exposed_state(self):
        return self.process.state

    def exposed_time(self):
        return self.process.clock.time

    def exposed_shut_down(self):
        logger.info(f"Shutting down process with id {self.process.id}")
        sys.exit(0)

    def exposed_message(self, message: str):
        response = self.process.handle_message(Message.deserialize(message))
        if isinstance(response, Message):
            return response.serialize()
        return response


class Sender:
    def send(self, message: Message, port: int):
        with rpyc.connect("localhost", port) as conn:
            response = conn.root.message(message.serialize())
            if isinstance(response, str):
                return Message.deserialize(response)
            return response

    def use_resource(self, port: int):
        with rpyc.connect("localhost", port) as conn:
            return conn.root.use()


@dataclass(frozen=True)
class Message:
    type: MessageType
    sender_id: int
    time: int

    def serialize(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def deserialize(cls, serialized: str) -> Message:
        values = json.loads(serialized)
        values["type"] = MessageType(values["type"])
        return cls(**values)


class Process(Thread):
    def __init__(self, id: int, resource_port: int, other_processes: List[int]):
        super().__init__()
        self.id = id

        self.clock: LamportClock = LamportClock()
        self.state: State = State.DO_NOT_WANT
        self.sent_message: Optional[Message] = None

        self.t_p = 5

        self.queue = ResponseQueue()
        self.waiting = Requests()

        self.sender = Sender()

        self.resource_port = resource_port
        self.other_processes = other_processes

    def handle_request(self, message: Message) -> Optional[Message]:
        self.clock.increment(message.time)

        if (
                self.state == State.HELD or
                (self.state == State.WANTED and
                 (self.sent_message.time < message.time or
                  (self.sent_message.time == message.time and self.id < message.sender_id)
                 )
                )
        ):
            logger.info(f"{self.id} ignoring request")
            self.queue.add(message)
            return None

        reply = Message(MessageType.REPLY, self.id, self.clock.increment())
        logger.info(f"{self.id} replying with {reply}")
        return reply

    def handle_reply(self, message: Message):
        self.clock.increment(message.time)
        self.waiting.remove(message.sender_id)

    def handle_message(self, message: Message):
        logger.info(f"{self.id} received message {message}")
        if message.type == MessageType.REQUEST:
            return self.handle_request(message)
        elif message.type == MessageType.REPLY:
            return self.handle_reply(message)
        else:
            raise Exception("Unknown message type")

    def send_request_message(self, message: Message, p_id: int):
        response = self.sender.send(message, p_id)
        logger.info(f"{self.id} received reply {response}")
        if response is None:
            self.waiting.add(p_id)
        else:
            self.clock.increment(response.time)

    def request_resource(self) -> None:
        if self.state != State.DO_NOT_WANT:
            raise Exception

        msg = Message(MessageType.REQUEST, self.id, self.clock.increment())
        self.sent_message = msg
        self.state = State.WANTED

        for p in self.other_processes:
            self.send_request_message(msg, p)

        while self.waiting.is_waiting():
            logger.info(f"{self.id} waiting for {self.waiting.requests}")
            time.sleep(1)
            pass

    def use_resource(self) -> None:
        self.state = State.HELD
        self.sender.use_resource(self.resource_port)

    def free_resource(self):
        self.state = State.DO_NOT_WANT
        self.sent_message = None

        while len(self.queue) > 0:
            message = self.queue.pop()
            self.sender.send(Message(MessageType.REPLY, self.id, self.clock.increment()), message.sender_id)

    def _start_server(self):
        service = classpartial(ProcessService, self)
        server = ThreadedServer(service, port=self.id)
        thread = Thread(target=server.start)
        thread.daemon = True
        thread.start()

    def run(self) -> None:
        self._start_server()
        while True:
            time.sleep(randint(5, self.t_p))
            logger.info(f"{self.id} requesting resource")
            self.request_resource()
            logger.info(f"{self.id} using resource")
            self.use_resource()
            logger.info(f"{self.id} freeing resource")
            self.free_resource()


def create_process(port: int, resource_port: int, other_process_ports):
    p = Process(port, resource_port, other_process_ports)
    p.daemon = True
    p.start()
    p.join()

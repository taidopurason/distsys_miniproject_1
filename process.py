from __future__ import annotations

import json
import logging
from dataclasses import dataclass, asdict
from enum import Enum
from threading import Lock, Thread, Event
from random import randint

from typing import Optional, Dict

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

    def exposed_message(self, message: str):
        response = self.process.handle_message(Message.deserialize(message))
        if isinstance(response, Message):
            return response.serialize()
        return response


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
    def __init__(self, process_id: int, resource_port: int, id_to_port: Dict[int, int]):
        super().__init__()
        self.id = process_id

        self.clock: LamportClock = LamportClock()
        self.state: State = State.DO_NOT_WANT
        self.sent_message: Optional[Message] = None

        self._time = 5

        self.queue = ResponseQueue()
        self.waiting = Requests()

        self.id_to_port = id_to_port

        self.resource_port = resource_port

        self.other_processes = set(self.id_to_port.keys()) - {self.id}
        if self.id not in self.id_to_port:
            raise Exception("Process id is missing from id to port map.")

    def set_time(self, t):
        if t < T_LOWER:
            raise Exception(f"time must be greater or equal to {T_LOWER}")
        self._time = t

    def _send_message(self, message: Message, target_id: int):
        with rpyc.connect("localhost", self.id_to_port[target_id]) as conn:
            response = conn.root.message(message.serialize())
            if isinstance(response, str):
                return Message.deserialize(response)
            return response

    def handle_request(self, message: Message) -> Optional[Message]:
        self.clock.increment(message.time)

        if (
                self.state == State.HELD or
                (self.state == State.WANTED and
                 (self.sent_message.time < message.time or
                 # id timestamps are the same, using id to break the tie
                  (self.sent_message.time == message.time and self.id < message.sender_id)
                 )
                )
        ):
            logger.info(f"P{self.id} ignoring request")
            self.queue.add(message)
            return None

        reply = Message(MessageType.REPLY, self.id, self.clock.increment())
        logger.info(f"P{self.id} replying with {reply}")
        return reply

    def handle_reply(self, message: Message):
        self.clock.increment(message.time)
        self.waiting.remove(message.sender_id)

    def handle_message(self, message: Message):
        logger.info(f"P{self.id} received message {message}")
        if message.type == MessageType.REQUEST:
            return self.handle_request(message)
        elif message.type == MessageType.REPLY:
            return self.handle_reply(message)
        else:
            raise Exception("Unknown message type")

    def send_request_message(self, message: Message, p_id: int):
        response = self._send_message(message, p_id)
        logger.info(f"P{self.id} received reply {response}")
        if response is None:
            self.waiting.add(p_id)
        else:
            self.clock.increment(response.time)

    def request_resource(self):
        if self.state != State.DO_NOT_WANT:
            raise Exception

        msg = Message(MessageType.REQUEST, self.id, self.clock.increment())
        self.sent_message = msg
        self.state = State.WANTED

        for p in self.other_processes:
            self.send_request_message(msg, p)

        while self.waiting.is_waiting():
            # Event().wait(1)
            pass

    def use_resource(self):
        self.state = State.HELD
        with rpyc.connect("localhost", self.resource_port) as conn:
            return conn.root.use()

    def free_resource(self):
        self.state = State.DO_NOT_WANT
        self.sent_message = None

        if len(self.queue) > 0:
            reply_message = Message(MessageType.REPLY, self.id, self.clock.increment())
            while len(self.queue) > 0:
                message = self.queue.pop()
                self._send_message(reply_message, message.sender_id)

    def _start_server(self):
        logger.info(f"P{self.id} starting server with port {self.id_to_port[self.id]}")
        service = classpartial(ProcessService, self)
        server = ThreadedServer(service, port=self.id_to_port[self.id])
        thread = Thread(target=server.start)
        thread.daemon = True
        thread.start()

    def run(self) -> None:
        self._start_server()
        while True:
            Event().wait(randint(5, self._time))
            logger.info(f"P{self.id} requesting resource")
            self.request_resource()
            logger.info(f"P{self.id} using resource")
            self.use_resource()
            logger.info(f"P{self.id} freeing resource")
            self.free_resource()

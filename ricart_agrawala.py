from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from typing import Optional


class State(Enum):
    HELD = "HELD"
    WANTED = "WANTED"
    DO_NOT_WANT = "DO-NOT-WANT"


@dataclass
class Process:
    id: int
    time: int = 0
    state: State = State.DO_NOT_WANT
    sent_message: Optional[RequestMessage] = None

    def request(self, message: RequestMessage) -> Message:
        self.time = max(message.time, self.time) + 1

        while not (
                self.state == State.DO_NOT_WANT or (
                self.state == State.WANTED and self.sent_message.time < message.time)
        ):
            pass

        return Message(self.time)

    def create_message(self) -> Message:
        self.time += 1

        msg = RequestMessage(self.time, self.id)
        self.sent_message = msg
        self.state = State.WANTED

        return msg


@dataclass()
class Message:
    time: int


@dataclass()
class RequestMessage(Message):
    process_id: int


@dataclass()
class Resource:
    current_user: Optional[Process] = None

    @property
    def is_used(self):
        return self.current_user is not None

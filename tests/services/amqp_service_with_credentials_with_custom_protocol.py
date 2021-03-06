import ujson
import asyncio
import os
import signal
import tomodachi
import uuid
from typing import Any, Dict, Tuple, Union
from tomodachi.transport.amqp import amqp, amqp_publish

data_uuid = str(uuid.uuid4())


class CustomProtocol(object):
    @classmethod
    async def build_message(cls, service: Any, topic: str, data: Any) -> str:
        message = {
            'protocol': 'custom',
            'data': data
        }
        return ujson.dumps(message)

    @classmethod
    async def parse_message(cls, payload: str) -> Union[Dict, Tuple]:
        message = ujson.loads(payload)
        return message, None, None


@tomodachi.service
class AWSSNSSQSService(tomodachi.Service):
    name = 'test_amqp'
    log_level = 'INFO'
    options = {
        'amqp': {
            'login': 'guest',
            'password': 'guest'
        }
    }
    closer = asyncio.Future()  # type: Any
    test_topic_data_received = False
    test_topic_data = None
    data_uuid = data_uuid

    def check_closer(self):
        if self.test_topic_data_received:
            if not self.closer.done():
                self.closer.set_result(None)

    @amqp('test.custom.topic', message_protocol=CustomProtocol)
    async def test(self, data: Any, protocol: Any, default_value: bool = True) -> None:
        if data == self.data_uuid and protocol == 'custom':
            self.test_topic_data_received = default_value
            self.test_topic_data = data

            self.check_closer()

    async def _started_service(self) -> None:
        async def publish(data: Any, routing_key: str) -> None:
            await amqp_publish(self, data, routing_key=routing_key, wait=False, message_protocol=CustomProtocol)

        async def _async() -> None:
            async def sleep_and_kill() -> None:
                await asyncio.sleep(10.0)
                if not self.closer.done():
                    self.closer.set_result(None)

            task = asyncio.ensure_future(sleep_and_kill())
            await self.closer
            if not task.done():
                task.cancel()
            os.kill(os.getpid(), signal.SIGINT)
        asyncio.ensure_future(_async())

        self.data_uuid = str(uuid.uuid4())
        await publish(self.data_uuid, 'test.custom.topic')

    def stop_service(self) -> None:
        if not self.closer.done():
            self.closer.set_result(None)

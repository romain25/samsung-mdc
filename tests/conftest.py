from typing import AsyncIterator
import sys
from unittest.mock import Mock
from asyncio import StreamReader, StreamWriter

import pytest_asyncio  # type: ignore[import-not-found]

from samsung_mdc import MDC
from samsung_mdc.connection import pack_payload, pack_response


class MDCMock(MDC):
    def __init__(self, target='mock', *args, **kwargs):
        super().__init__(target, *args, **kwargs)
        self.timeout = 1
        self.writer = Mock(spec=StreamWriter)
        if sys.version_info < (3, 8):
            # fix for Python 3.7
            async def drain():
                ...
            self.writer.drain  = drain

        self.reader = StreamReader()

    async def close(self):
        # Not closing connection so we can inspect self.writer mock afterwards
        ...

    def feed_response(self, command, display_id, data, ack=True):
        self.reader.feed_data(pack_response(
            command.CMD if command.SUBCMD is None
            else (command.CMD, command.SUBCMD),
            display_id, ack, data
        ))

    def assert_request(self, command, display_id, data):
        self.writer.write.assert_called_with(pack_payload(
            command.CMD if command.SUBCMD is None
            else (command.CMD, command.SUBCMD),
            display_id, data
        ))


class MDCMockSingleton(MDCMock):
    _singleton = None

    def __new__(cls, *args, **kwargs):
        if cls._singleton is None:
            cls._singleton = object.__new__(cls, *args, **kwargs)
        return cls._singleton

    def __init__(self, *args, **kwargs):
        # when overriding __new__ - __init__ applied anyway,
        # so we shouldn't recreate writer/reader for
        # MDCMockSingleton purposes
        writer, reader = self._singleton.writer, self._singleton.reader
        super().__init__(*args, **kwargs)
        self.writer = writer or self.writer
        self.reader = reader or self.reader


@pytest_asyncio.fixture
async def mdc_mock() -> AsyncIterator[MDCMockSingleton]:
    import samsung_mdc
    import samsung_mdc.cli

    # monkey patch
    samsung_mdc.MDC = MDCMockSingleton  # type: ignore[misc]
    samsung_mdc.cli.MDC = MDCMockSingleton  # type: ignore[misc]

    try:
        yield MDCMockSingleton()
    finally:
        samsung_mdc.MDC = MDC  # type: ignore[misc]
        samsung_mdc.cli.MDC = MDC  # type: ignore[misc]
        MDCMockSingleton._singleton = None

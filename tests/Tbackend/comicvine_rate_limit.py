import asyncio
import unittest

from backend.implementations import comicvine as comicvine_module
from backend.implementations.comicvine import ComicVine, _ComicVineRequestGate


class _FakeResponse:
    def __init__(self, status=200, result=None, headers=None):
        self.status = status
        self._result = result or {'status_code': 1, 'results': {}}
        self.headers = headers or {}

    async def json(self):
        return self._result


class _FakeSession:
    def __init__(self, first_status=200, delay=0.02):
        self.first_status = first_status
        self.delay = delay
        self.calls = 0
        self.active = 0
        self.max_active = 0

    async def get(self, url, params=None):
        self.calls += 1
        call_number = self.calls
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(self.delay)
            status = self.first_status if call_number == 1 else 200
            return _FakeResponse(status=status)
        finally:
            self.active -= 1


class ComicVineRateLimitTests(unittest.TestCase):
    def setUp(self):
        self.original_gate = comicvine_module._cv_request_gate
        comicvine_module._cv_request_gate = _ComicVineRequestGate(
            min_interval=0.0,
            cooldown=60.0
        )
        self.comicvine = ComicVine.__new__(ComicVine)
        self.comicvine._params = {}
        self.call_api = self.comicvine._ComicVine__call_api

    def tearDown(self):
        comicvine_module._cv_request_gate = self.original_gate

    def test_metadata_requests_are_serialized(self):
        async def run_test():
            session = _FakeSession()
            await asyncio.gather(*(
                self.call_api(session, '/volume/4050-1')
                for _ in range(3)
            ))
            return session

        session = asyncio.run(run_test())
        self.assertEqual(session.calls, 3)
        self.assertEqual(session.max_active, 1)

    def test_http_420_stops_queued_requests(self):
        default = {'results': []}

        async def run_test():
            session = _FakeSession(first_status=420)
            results = await asyncio.gather(
                self.call_api(
                    session,
                    '/volume/4050-1',
                    default=default
                ),
                self.call_api(
                    session,
                    '/volume/4050-2',
                    default=default
                )
            )
            return session, results

        session, results = asyncio.run(run_test())
        self.assertEqual(session.calls, 1)
        self.assertEqual(results, [default, default])


if __name__ == '__main__':
    unittest.main()

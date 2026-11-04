import http.client
import socket
import time
import unittest
from contextlib import closing
from threading import Thread
from unittest.mock import patch

from flask import Flask
from waitress import wasyncore
from waitress.server import MultiSocketServer, create_server
from waitress.task import ThreadedTaskDispatcher

from backend.internals.server import Server


class ServerShutdown(unittest.TestCase):
    def test_shutdown_closes_single_and_multiple_listeners_in_the_event_loop(self):
        for count in (1, 2):
            with self.subTest(listeners=count):
                sockets = [socket.socket() for _ in range(count)]
                for listener in sockets:
                    listener.bind(('127.0.0.1', 0))
                addresses = [listener.getsockname() for listener in sockets]
                server = object.__new__(Server)
                server.app = Flask(__name__)
                server.app.add_url_rule('/', view_func=lambda: 'ready')
                server._Server__start_type = None
                server_map = {}
                errors = []

                def make_server(app, **kwargs):
                    nonlocal server_map
                    kwargs.pop('host')
                    kwargs.pop('port')
                    server_map = kwargs.setdefault('map', {})
                    return create_server(app, sockets=sockets, **kwargs)

                def run():
                    try:
                        server.run('localhost', 0, '')
                    except Exception as error:
                        errors.append(error)

                thread = Thread(target=run, daemon=True)
                try:
                    with patch('backend.internals.server.create_server', side_effect=make_server), \
                        patch('backend.internals.server.ThreadedTaskDispatcher', ThreadedTaskDispatcher):
                        thread.start()
                        deadline = time.monotonic() + 3
                        while not hasattr(server, 'server') and not errors:
                            self.assertLess(time.monotonic(), deadline)
                            time.sleep(0.01)
                        self.assertEqual(errors, [])
                        self.assertEqual(isinstance(server.server, MultiSocketServer), count == 2)
                        for address in addresses:
                            with closing(http.client.HTTPConnection(*address, timeout=2)) as client:
                                client.request('GET', '/')
                                self.assertEqual(client.getresponse().read(), b'ready')
                        server._Server__trigger_server_shutdown()
                        thread.join(timeout=3)
                        self.assertFalse(thread.is_alive(), 'Shutdown left the server event loop running')
                        self.assertEqual(errors, [])
                        self.assertFalse(server_map)
                        self.assertTrue(all(listener.fileno() == -1 for listener in sockets))
                finally:
                    if hasattr(server, 'server'):
                        server.server.task_dispatcher.shutdown()
                    wasyncore.close_all(server_map)
                    for listener in sockets:
                        listener.close()
                    thread.join(timeout=2)


if __name__ == '__main__':
    unittest.main()

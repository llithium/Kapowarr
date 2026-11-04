#!/usr/bin/env python3
"""Verify that closing the last browser connection stops every app process."""

import argparse
import html
import json
import os
import re
import selectors
import signal
import socket
import sqlite3
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket
from smoke_test import fetch, wait_for


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app', type=Path)
    args = parser.parse_args()
    launcher = args.app.resolve() / 'Contents/MacOS/Kapowarr'
    with tempfile.TemporaryDirectory(prefix='kapowarr-browser-close-') as folder:
        data = Path(folder)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        with sqlite3.connect(data / 'Kapowarr.db') as connection:
            connection.execute('CREATE TABLE config(key PRIMARY KEY, value BLOB)')
            connection.executemany('INSERT INTO config VALUES (?, ?)', [
                ('port', port), ('downloads_enabled', False)
            ])
        process = subprocess.Popen(
            [str(launcher), '--browser-session-app-test'],
            env={'HOME': str(Path.home()), 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin',
                 'KAPOWARR_DATA_DIR': folder},
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        backend_pid = None
        clients = []
        try:
            assert process.stdout is not None
            with selectors.DefaultSelector() as output:
                output.register(process.stdout, selectors.EVENT_READ)
                assert output.select(timeout=15), 'Launcher did not report startup.'
            line = process.stdout.readline().strip()
            assert line.startswith('SERVER_PID='), line
            backend_pid = int(line.split('=', 1)[1])
            url = f'http://127.0.0.1:{port}'
            wait_for(url, process)
            page = fetch(url).decode()
            session_url = re.search(r'data-session-url="([^"]+)"', page)
            protocol = re.search(r'data-session-protocol="([^"]+)"', page)
            assert session_url and protocol, 'Browser close is not connected to the app lifetime.'
            with sqlite3.connect(data / 'Kapowarr.db') as connection:
                api_key = connection.execute("SELECT value FROM config WHERE key='api_key'").fetchone()[0]
            settings_url = f'{url}/api/settings?api_key={api_key}'

            def set_quit_on_close(enabled):
                request = urllib.request.Request(
                    settings_url, method='PUT',
                    data=json.dumps({'quit_on_browser_close': enabled}).encode(),
                    headers={'Content-Type': 'application/json'}
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    assert json.load(response)['result']['quit_on_browser_close'] is enabled

            assert json.loads(fetch(settings_url))['result']['quit_on_browser_close'] is True
            assert b'quit-on-browser-close-input' in fetch(url + '/settings/general')

            def connect():
                client = websocket.create_connection(
                    html.unescape(session_url.group(1)),
                    subprotocols=[html.unescape(protocol.group(1))],
                    timeout=3, http_no_proxy=['127.0.0.1']
                )
                clients.append(client)
                return client

            first, second = connect(), connect()
            first.close()
            time.sleep(6)
            assert process.poll() is None, 'Closing one of two tabs stopped the app.'
            second.close()
            time.sleep(1)
            replacement = connect()
            time.sleep(6)
            assert process.poll() is None, 'Reloading or navigating stopped the app.'
            set_quit_on_close(False)
            replacement.close()
            time.sleep(6)
            assert process.poll() is None, 'The disabled setting still quit the app.'
            final = connect()
            set_quit_on_close(True)
            final.close()
            process.communicate(timeout=12)
            assert process.returncode == 0, process.returncode
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline:
                try:
                    os.killpg(backend_pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.1)
            else:
                raise AssertionError('Server or worker processes survived the last tab closing.')
            print('Multiple tabs, navigation, and the disabled setting stay running; enabling last-tab quit stops the app and every worker.')
        finally:
            for client in clients:
                client.close()
            if process.poll() is None:
                process.kill()
                process.wait()
            if backend_pid is not None:
                try:
                    os.killpg(backend_pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass


if __name__ == '__main__':
    main()

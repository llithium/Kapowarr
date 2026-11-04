#!/usr/bin/env python3
"""Verify a built app using an isolated database and only bundled Python."""

import argparse
import json
import os
import signal
import socket
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path


def fetch(url: str, body=None) -> bytes:
    payload = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(request, timeout=5).read()


def wait_for(url: str, process: subprocess.Popen) -> None:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f'Launcher exited before startup: {process.returncode}')
        try:
            fetch(url)
            return
        except (OSError, urllib.error.URLError):
            time.sleep(0.25)
    raise RuntimeError(f'Server did not become ready: {url}')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('app', type=Path)
    parser.add_argument('--database', type=Path, help='Test a temporary copy of an existing database.')
    args = parser.parse_args()
    app = args.app.resolve()
    server = app / 'Contents/Resources/server/kapowarr-server'
    launcher = app / 'Contents/MacOS/Kapowarr'
    # Exclude Homebrew, installed Python, and user Python configuration.
    environment = {'HOME': str(Path.home()), 'PATH': '/usr/bin:/bin:/usr/sbin:/sbin'}
    subprocess.run([str(server), '--check-bundle'], env=environment, check=True, timeout=30)
    with tempfile.TemporaryDirectory(prefix='kapowarr-app-test-') as temporary:
        data = Path(temporary)
        fixture = Path(__file__).resolve().parents[2] / 'tests/fixtures/macos/comic.cbr'
        unrar = app / 'Contents/Resources/server/_internal/backend/lib/unrar'
        subprocess.run([str(unrar), 'x', '-inul', str(fixture), str(data) + '/'],
                       env=environment, check=True, timeout=10)
        assert (data / 'page.txt').read_text() == 'Kapowarr archive extraction test.\n'
        downloads = data / 'downloads'
        downloads.mkdir()
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
        database = data / 'Kapowarr.db'
        original_counts = {}
        with sqlite3.connect(database) as connection:
            if args.database:
                source = sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True)
                try:
                    source.backup(connection)
                finally:
                    source.close()
                # The copied library must not start downloads or contact indexers.
                connection.execute('UPDATE task_intervals SET next_run=?', (round(time.time()) + 86400,))
                original_counts = {
                    table: connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
                    for table in ('volumes', 'issues', 'files')
                }
            else:
                connection.execute('CREATE TABLE config(key PRIMARY KEY, value BLOB)')
            connection.executemany('INSERT OR REPLACE INTO config VALUES (?, ?)', [
                ('port', port), ('downloads_enabled', False), ('download_folder', str(downloads))
            ])
        environment['KAPOWARR_DATA_DIR'] = str(data)
        process = subprocess.Popen(
            [str(launcher), '--smoke-test', '18'], env=environment,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        backend_pid = None
        try:
            assert process.stdout is not None
            line = process.stdout.readline().strip()
            if not line.startswith('SERVER_PID='):
                raise RuntimeError(f'Launcher did not start: {line}')
            backend_pid = int(line.split('=', 1)[1])
            url = f'http://127.0.0.1:{port}'
            wait_for(url, process)
            assert b'<svg' in fetch(url + '/static/img/favicon.svg')
            with sqlite3.connect(database) as connection:
                auth = connection.execute("SELECT value FROM config WHERE key='api_key'").fetchone()[0]
            api = f'?api_key={auth}'
            about = json.loads(fetch(url + '/api/system/about' + api))['result']
            assert about['database_location'] == str(database), about
            assert about['data_folder'].startswith(str(app)), about
            assert fetch(url + '/api/system/database' + api).startswith(b'SQLite format 3')
            # A second launcher must fail instead of opening the same database.
            duplicate = subprocess.run(
                [str(launcher), '--smoke-test', '1'], env=environment,
                capture_output=True, text=True, timeout=10
            )
            assert duplicate.returncode != 0 and 'already running' in duplicate.stderr
            fetch(url + '/api/system/power/restart' + api, {})
            time.sleep(2)
            wait_for(url, process)
            # All temporary data belongs outside the application bundle.
            with sqlite3.connect(database) as connection:
                assert connection.execute("SELECT value FROM config WHERE key='download_folder'").fetchone()[0] == str(downloads)
                for table, count in original_counts.items():
                    assert connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] == count
            output, _ = process.communicate(timeout=45)
            assert process.returncode == 0, output
            assert 'Server stopped.' in output, output
            try:
                os.kill(backend_pid, 0)
            except ProcessLookupError:
                pass
            else:
                raise AssertionError('Backend outlived its launcher')
            with socket.socket() as listener:
                listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                listener.bind(('127.0.0.1', port))
            print('App startup, web assets, database export, restart, duplicate protection, and clean shutdown passed.')
        except Exception:
            log = data / 'logs/launcher.log'
            if log.exists():
                print(log.read_text()[-6000:], flush=True)
            raise
        finally:
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

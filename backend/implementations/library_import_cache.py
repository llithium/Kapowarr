# -*- coding: utf-8 -*-

"""Persistent cache for expensive Library Import discovery work.

The cache is intentionally best-effort. Library Import must continue to work if
there is no Flask application context, no configured database, or the cache
cannot be read. Checkpoints use a separate SQLite sidecar so a long iCloud-backed
scan can be interrupted and resumed without reopening already-inspected comic
archives on the next run.
"""

from contextlib import contextmanager
from json import dumps, loads
from os import stat
from sqlite3 import Connection, DatabaseError, connect
from time import time
from typing import (TYPE_CHECKING, Any, Dict, Iterable,
                    Iterator, Optional, Tuple)

from flask import has_app_context

from backend.internals.db import DBConnection

if TYPE_CHECKING:
    from backend.implementations.comicinfo import ComicInfoData


# Bump this when ComicInfo parsing semantics change in a way that should force
# archives to be inspected again.
COMICINFO_CACHE_VERSION = 1

# ComicVine volume metadata can change for ongoing series, so unlike the stable
# issue -> parent-volume mapping it gets a finite lifetime.
CV_VOLUME_CACHE_TTL = 24 * 60 * 60

_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS library_import_comicinfo_cache(
    filepath TEXT PRIMARY KEY,
    size INTEGER NOT NULL,
    modified_ns INTEGER NOT NULL,
    parser_version INTEGER NOT NULL,
    metadata_json TEXT NOT NULL,
    cached_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS library_import_cv_issue_cache(
    issue_id INTEGER PRIMARY KEY,
    volume_id INTEGER NOT NULL,
    cached_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS library_import_cv_volume_cache(
    volume_id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    year INTEGER,
    issue_count INTEGER NOT NULL,
    site_url TEXT NOT NULL,
    cached_at INTEGER NOT NULL
);
"""

_COMICINFO_FIELD_TYPES = {
    'series': str,
    'title': str,
    'issue_number': str,
    'volume': int,
    'issue_count': int,
    'year': int,
    'month': int,
    'day': int,
    'publisher': str,
    'format': str,
    'web': str,
    'gtin': str,
    'alternate_series': str,
    'comicvine_issue_id': int,
    'comicvine_volume_id': int,
}


def _valid_comicinfo_cache_value(value: Any) -> bool:
    """Reject stale or malformed JSON before it reaches import matching."""
    if not isinstance(value, dict) or not value:
        return False

    return all(
        key in _COMICINFO_FIELD_TYPES
        and isinstance(field_value, _COMICINFO_FIELD_TYPES[key])
        and not isinstance(field_value, bool)
        for key, field_value in value.items()
    )


@contextmanager
def _cache_db() -> Iterator[Optional[Connection]]:
    """Open disposable cache storage independently of application transactions.

    The sidecar is derived from the configured database path and can be rebuilt.
    Schema setup belongs to this connection, so cache checkpoints never commit
    unrelated library changes and no process-global schema flag can go stale.
    """
    connection = None
    if has_app_context() and DBConnection.default_file:
        try:
            connection = connect(DBConnection.default_file + '.import-cache')
            connection.executescript(_CACHE_SCHEMA)
        except DatabaseError:
            if connection is not None:
                connection.close()
            connection = None

    try:
        if connection is None:
            yield None
        else:
            with connection:
                yield connection
    finally:
        if connection is not None:
            connection.close()


def _file_signature(filepath: str) -> Optional[Tuple[int, int]]:
    """Return a cheap signature that does not require opening archive data."""
    try:
        info = stat(filepath)
    except OSError:
        return None

    modified_ns = getattr(
        info,
        'st_mtime_ns',
        int(info.st_mtime * 1_000_000_000)
    )
    return info.st_size, modified_ns


def get_cached_comicinfo(
    filepath: str
) -> Optional['ComicInfoData']:
    """Return cached positive ComicInfo metadata for an unchanged file.

    Only successful ComicInfo parses are cached. A transient iCloud/open error
    therefore cannot poison the cache with a permanent "no metadata" result.
    """
    signature = _file_signature(filepath)
    if signature is None:
        return None

    try:
        with _cache_db() as connection:
            if connection is None:
                return None
            row = connection.execute(
                """
                SELECT metadata_json
                FROM library_import_comicinfo_cache
                WHERE filepath = ?
                  AND size = ?
                  AND modified_ns = ?
                  AND parser_version = ?
                LIMIT 1;
                """,
                (
                    filepath,
                    signature[0],
                    signature[1],
                    COMICINFO_CACHE_VERSION
                )
            ).fetchone()
    except (DatabaseError, RuntimeError):
        return None

    if row is None:
        return None

    try:
        value = loads(row[0])
    except (TypeError, ValueError):
        return None

    return value if _valid_comicinfo_cache_value(value) else None


def store_cached_comicinfo(
    filepath: str,
    metadata: 'ComicInfoData'
) -> None:
    """Persist one successfully parsed archive immediately.

    Committing each positive parse is deliberate: if an iCloud scan is stopped
    after hundreds of files, those files remain checkpointed for the next run.
    """
    if not metadata:
        return

    signature = _file_signature(filepath)
    if signature is None:
        return

    try:
        with _cache_db() as connection:
            if connection is None:
                return
            connection.execute(
                """
                INSERT INTO library_import_comicinfo_cache(
                    filepath,
                    size,
                    modified_ns,
                    parser_version,
                    metadata_json,
                    cached_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(filepath) DO UPDATE SET
                    size = excluded.size,
                    modified_ns = excluded.modified_ns,
                    parser_version = excluded.parser_version,
                    metadata_json = excluded.metadata_json,
                    cached_at = excluded.cached_at;
                """,
                (
                    filepath,
                    signature[0],
                    signature[1],
                    COMICINFO_CACHE_VERSION,
                    dumps(metadata, separators=(',', ':'), sort_keys=True),
                    int(time())
                )
            )
    except (DatabaseError, RuntimeError):
        return


def get_cached_issue_volume_ids(issue_ids: Iterable[int]) -> Dict[int, int]:
    """Return cached ComicVine issue -> parent volume mappings."""
    ids = sorted(set(issue_ids))
    if not ids:
        return {}

    placeholders = ','.join('?' for _ in ids)
    try:
        with _cache_db() as connection:
            if connection is None:
                return {}
            rows = connection.execute(
                f"""
                SELECT issue_id, volume_id
                FROM library_import_cv_issue_cache
                WHERE issue_id IN ({placeholders});
                """,
                ids
            ).fetchall()
    except (DatabaseError, RuntimeError):
        return {}

    return {
        int(row[0]): int(row[1])
        for row in rows
    }


def store_issue_volume_ids(mapping: Dict[int, int]) -> None:
    """Persist stable ComicVine issue -> parent volume mappings."""
    if not mapping:
        return

    now = int(time())
    try:
        with _cache_db() as connection:
            if connection is None:
                return
            connection.executemany("""
                INSERT INTO library_import_cv_issue_cache(issue_id, volume_id, cached_at)
                VALUES (?, ?, ?)
                ON CONFLICT(issue_id) DO UPDATE SET
                    volume_id = excluded.volume_id,
                    cached_at = excluded.cached_at;
                """, ((issue_id, volume_id, now)
                   for issue_id, volume_id in mapping.items()))
    except (DatabaseError, RuntimeError):
        return


def get_cached_cv_volumes(
    volume_ids: Iterable[int]
) -> Dict[int, Dict[str, Any]]:
    """Return recently cached exact ComicVine volume metadata."""
    ids = sorted(set(volume_ids))
    if not ids:
        return {}

    placeholders = ','.join('?' for _ in ids)
    cutoff = int(time()) - CV_VOLUME_CACHE_TTL
    try:
        with _cache_db() as connection:
            if connection is None:
                return {}
            rows = connection.execute(
                f"""
                SELECT volume_id, title, year, issue_count, site_url
                FROM library_import_cv_volume_cache
                WHERE volume_id IN ({placeholders})
                  AND cached_at >= ?;
                """,
                (*ids, cutoff)
            ).fetchall()
    except (DatabaseError, RuntimeError):
        return {}

    return {
        int(row[0]): {
            'comicvine_id': int(row[0]),
            'title': row[1],
            'year': row[2],
            'issue_count': int(row[3]),
            'site_url': row[4],
            # Existing-library matching runs before direct ComicInfo lookup, so
            # a cached direct result reaching this point is not already added.
            'already_added': None
        }
        for row in rows
    }


def store_cached_cv_volumes(volumes: Iterable[Dict[str, Any]]) -> None:
    """Persist exact ComicVine volume metadata used by direct-ID matching."""
    rows = []
    now = int(time())
    for volume in volumes:
        try:
            rows.append((
                int(volume['comicvine_id']),
                str(volume['title']),
                volume.get('year'),
                int(volume['issue_count']),
                str(volume['site_url']),
                now
            ))
        except (KeyError, TypeError, ValueError):
            continue

    if not rows:
        return

    try:
        with _cache_db() as connection:
            if connection is None:
                return
            connection.executemany(
                """
                INSERT INTO library_import_cv_volume_cache(
                    volume_id, title, year, issue_count, site_url, cached_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(volume_id) DO UPDATE SET
                    title = excluded.title,
                    year = excluded.year,
                    issue_count = excluded.issue_count,
                    site_url = excluded.site_url,
                    cached_at = excluded.cached_at;
                """,
                rows
            )
    except (DatabaseError, RuntimeError):
        return

# -*- coding: utf-8 -*-

"""Persistent cache for expensive Library Import discovery work.

The cache is intentionally best-effort. Library Import must continue to work if
there is no Flask application context, no configured database, or the cache
cannot be read. Cache writes are committed immediately so a long iCloud-backed
scan can be interrupted and resumed without reopening already-inspected comic
archives on the next run.
"""

from json import dumps, loads
from os import stat
from sqlite3 import DatabaseError
from time import time
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional, Set, Tuple

from flask import has_app_context

from backend.internals.db import DBConnection, commit, get_db

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

_schema_ready_for: Set[str] = set()


def _ensure_schema() -> bool:
    """Create cache tables lazily when running inside the Kapowarr web app."""
    if not has_app_context() or not DBConnection.file:
        return False

    db_file = DBConnection.file
    if db_file in _schema_ready_for:
        return True

    try:
        get_db().executescript(_CACHE_SCHEMA)
        commit()
    except (DatabaseError, RuntimeError):
        return False

    _schema_ready_for.add(db_file)
    return True


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
    if signature is None or not _ensure_schema():
        return None

    try:
        row = get_db().execute(
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

    return value if isinstance(value, dict) and value else None


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
    if signature is None or not _ensure_schema():
        return

    try:
        get_db().execute(
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
        commit()
    except (DatabaseError, RuntimeError):
        return


def get_cached_issue_volume_ids(issue_ids: Iterable[int]) -> Dict[int, int]:
    """Return cached ComicVine issue -> parent volume mappings."""
    ids = sorted(set(issue_ids))
    if not ids or not _ensure_schema():
        return {}

    placeholders = ','.join('?' for _ in ids)
    try:
        rows = get_db().execute(
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
    if not mapping or not _ensure_schema():
        return

    now = int(time())
    try:
        get_db().executemany(
            """
            INSERT INTO library_import_cv_issue_cache(issue_id, volume_id, cached_at)
            VALUES (?, ?, ?)
            ON CONFLICT(issue_id) DO UPDATE SET
                volume_id = excluded.volume_id,
                cached_at = excluded.cached_at;
            """,
            ((issue_id, volume_id, now) for issue_id, volume_id in mapping.items())
        )
        commit()
    except (DatabaseError, RuntimeError):
        return


def get_cached_cv_volumes(
    volume_ids: Iterable[int]
) -> Dict[int, Dict[str, Any]]:
    """Return recently cached exact ComicVine volume metadata."""
    ids = sorted(set(volume_ids))
    if not ids or not _ensure_schema():
        return {}

    placeholders = ','.join('?' for _ in ids)
    cutoff = int(time()) - CV_VOLUME_CACHE_TTL
    try:
        rows = get_db().execute(
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

    if not rows or not _ensure_schema():
        return

    try:
        get_db().executemany(
            """
            INSERT INTO library_import_cv_volume_cache(
                volume_id,
                title,
                year,
                issue_count,
                site_url,
                cached_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(volume_id) DO UPDATE SET
                title = excluded.title,
                year = excluded.year,
                issue_count = excluded.issue_count,
                site_url = excluded.site_url,
                cached_at = excluded.cached_at;
            """,
            rows
        )
        commit()
    except (DatabaseError, RuntimeError):
        return

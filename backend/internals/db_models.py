# -*- coding: utf-8 -*-

"""
Interacting with the database
"""

from os import stat
from typing import Dict, Iterable, List, Union

from backend.base.custom_exceptions import FileNotFound
from backend.base.definitions import FileData, GeneralFileData
from backend.base.helpers import first_of_subarrays
from backend.base.logging import LOGGER
from backend.internals.db import get_db


class FilesDB:
    @staticmethod
    def fetch(
        *,
        volume_id: Union[int, None] = None,
        issue_id: Union[int, None] = None,
        file_id: Union[int, None] = None,
        filepath: Union[str, None] = None
    ) -> List[FileData]:

        cursor = get_db()
        if volume_id:
            cursor.execute("""
                SELECT DISTINCT f.id, filepath, size
                FROM files f
                INNER JOIN issues_files if
                INNER JOIN issues i
                ON
                    f.id = if.file_id
                    AND if.issue_id = i.id
                WHERE volume_id = ?
                ORDER BY filepath;
                """,
                (volume_id,)
            )

        elif issue_id:
            cursor.execute("""
                SELECT DISTINCT f.id, filepath, size
                FROM files f
                INNER JOIN issues_files if
                ON f.id = if.file_id
                WHERE if.issue_id = ?
                ORDER BY filepath;
                """,
                (issue_id,)
            )

        elif file_id:
            cursor.execute("""
                SELECT id, filepath, size
                FROM files f
                WHERE f.id = ?
                LIMIT 1;
                """,
                (file_id,)
            )

        elif filepath:
            cursor.execute("""
                SELECT id, filepath, size
                FROM files f
                WHERE f.filepath = ?
                LIMIT 1;
                """,
                (filepath,)
            )

        else:
            cursor.execute("""
                SELECT id, filepath, size
                FROM files
                ORDER BY filepath;
                """
            )

        result: List[FileData] = cursor.fetchalldict() # type: ignore

        if (file_id or filepath) and not result:
            raise FileNotFound(file_id or filepath or '')

        return result

    @staticmethod
    def volume_of_file(filepath: str) -> Union[int, None]:
        volume_id = get_db().execute("""
            SELECT i.volume_id
            FROM
                files f
                INNER JOIN issues_files if
                INNER JOIN issues i
            ON
                f.id = if.file_id
                AND if.issue_id = i.id
            WHERE f.filepath = ?
            LIMIT 1;
            """,
            (filepath,)
        ).fetchone()

        if not volume_id:
            volume_id = get_db().execute("""
                SELECT vf.volume_id
                FROM
                    files f
                    INNER JOIN volume_files vf
                ON
                    f.id = vf.file_id
                WHERE f.filepath = ?
                LIMIT 1;
                """,
                (filepath,)
            ).fetchone()

        if not volume_id:
            return None
        return volume_id[0]

    @staticmethod
    def issues_covered(filepath: str) -> List[float]:
        return first_of_subarrays(get_db().execute("""
            SELECT DISTINCT
                i.calculated_issue_number
            FROM issues i
            INNER JOIN issues_files if
            INNER JOIN files f
            ON
                i.id = if.issue_id
                AND if.file_id = f.id
            WHERE f.filepath = ?
            ORDER BY calculated_issue_number;
            """,
            (filepath,)
        ))

    @staticmethod
    def add_file(
        filepath: str
    ) -> int:
        cursor = get_db()
        cursor.execute(
            "INSERT OR IGNORE INTO files(filepath, size) VALUES (?,?)",
            (filepath, stat(filepath).st_size)
        )

        if cursor.rowcount:
            LOGGER.debug(f'Added file to the database: {filepath}')
            return cursor.lastrowid

        return FilesDB.fetch(filepath=filepath)[0]["id"]

    @staticmethod
    def update_filepaths(old_to_new_mapping: Dict[str, str]) -> None:
        """Update filepaths after files have been moved/renamed.

        A destination filepath can already exist in the database even when the
        destination does not exist on disk. This can happen after restoring or
        migrating a Kapowarr database whose file table still contains stale
        paths. A plain ``UPDATE`` then violates the UNIQUE constraint on
        ``files.filepath`` after the filesystem rename has already succeeded.

        Temporarily move all source rows out of the filepath namespace first so
        swaps/chained renames are safe. If a non-source destination row already
        exists, merge that stale row's links into the source row before assigning
        the final filepath.
        """
        if not old_to_new_mapping:
            return

        cursor = get_db()
        staged_files: Dict[str, tuple] = {}

        # Stage source rows under guaranteed-unique database-only paths. This
        # frees destinations that are also sources in the same rename batch.
        for old, new in old_to_new_mapping.items():
            if old == new:
                continue

            file_row = cursor.execute(
                "SELECT id FROM files WHERE filepath = ? LIMIT 1;",
                (old,)
            ).fetchone()
            if file_row is None:
                continue

            file_id = file_row[0]
            temporary_path = f'{old}.kapowarr-db-rename-{file_id}'
            while cursor.execute(
                "SELECT 1 FROM files WHERE filepath = ? LIMIT 1;",
                (temporary_path,)
            ).fetchone():
                temporary_path += '_'

            cursor.execute(
                "UPDATE files SET filepath = ? WHERE id = ?;",
                (temporary_path, file_id)
            )
            staged_files[old] = (file_id, new)

        for old, (source_id, new) in staged_files.items():
            target_row = cursor.execute(
                "SELECT id FROM files WHERE filepath = ? LIMIT 1;",
                (new,)
            ).fetchone()

            if target_row is not None:
                target_id = target_row[0]
                if target_id != source_id:
                    LOGGER.warning(
                        'Merging duplicate file database rows during rename: '
                        '%s -> %s',
                        old,
                        new
                    )

                    # Preserve all issue bindings from the stale destination,
                    # including manual/forced matches.
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO issues_files(
                            file_id, issue_id, forced
                        )
                        SELECT ?, issue_id, forced
                        FROM issues_files
                        WHERE file_id = ?;
                        """,
                        (source_id, target_id)
                    )
                    cursor.execute(
                        """
                        UPDATE issues_files
                        SET forced = 1
                        WHERE file_id = ?
                            AND issue_id IN (
                                SELECT issue_id
                                FROM issues_files
                                WHERE file_id = ?
                                    AND forced = 1
                            );
                        """,
                        (source_id, target_id)
                    )

                    source_general = cursor.execute(
                        """
                        SELECT volume_id, file_type, forced
                        FROM volume_files
                        WHERE file_id = ?
                        LIMIT 1;
                        """,
                        (source_id,)
                    ).fetchone()
                    target_general = cursor.execute(
                        """
                        SELECT volume_id, file_type, forced
                        FROM volume_files
                        WHERE file_id = ?
                        LIMIT 1;
                        """,
                        (target_id,)
                    ).fetchone()

                    if source_general is None and target_general is not None:
                        cursor.execute(
                            """
                            INSERT INTO volume_files(
                                file_id, volume_id, file_type, forced
                            ) VALUES (?, ?, ?, ?);
                            """,
                            (
                                source_id,
                                target_general[0],
                                target_general[1],
                                target_general[2]
                            )
                        )
                    elif (
                        source_general is not None
                        and target_general is not None
                        and target_general[2]
                        and not source_general[2]
                        and source_general[:2] == target_general[:2]
                    ):
                        cursor.execute(
                            """
                            UPDATE volume_files
                            SET forced = 1
                            WHERE file_id = ?;
                            """,
                            (source_id,)
                        )

                    cursor.execute(
                        "DELETE FROM issues_files WHERE file_id = ?;",
                        (target_id,)
                    )
                    cursor.execute(
                        "DELETE FROM volume_files WHERE file_id = ?;",
                        (target_id,)
                    )
                    cursor.execute(
                        "DELETE FROM files WHERE id = ?;",
                        (target_id,)
                    )

            cursor.execute(
                "UPDATE files SET filepath = ? WHERE id = ?;",
                (new, source_id)
            )

        return

    @staticmethod
    def delete_file(
        file_id: int
    ) -> None:
        get_db().execute(
            "DELETE FROM files WHERE id = ?;",
            (file_id,)
        )
        return

    @staticmethod
    def delete_filepath(
        filepath: str
    ) -> None:
        get_db().execute(
            "DELETE FROM files WHERE filepath = ?;",
            (filepath,)
        )
        return

    @staticmethod
    def delete_filepaths(
        filepaths: Iterable[str]
    ) -> None:
        get_db().executemany(
            "DELETE FROM files WHERE filepath = ?;",
            ((filepath,) for filepath in filepaths)
        )
        return

    @staticmethod
    def delete_linked_files(volume_id: int) -> None:
        get_db().execute(
            """
            DELETE FROM files
            WHERE id IN (
                SELECT DISTINCT file_id
                FROM issues_files
                INNER JOIN issues
                ON issues_files.issue_id = issues.id
                WHERE volume_id = ?
            ) OR id IN (
                SELECT DISTINCT file_id
                FROM volume_files
                WHERE volume_id = ?
            );
            """,
            (volume_id, volume_id)
        )
        return

    @staticmethod
    def delete_issue_linked_files(issue_id: int) -> None:
        get_db().execute(
            """
            DELETE FROM files
            WHERE id in (
                SELECT DISTINCT file_id
                FROM issues_files
                WHERE issue_id = ?
            );
            """,
            (issue_id,)
        )

    @staticmethod
    def delete_unmatched_files() -> None:
        get_db().execute("""
            WITH ids AS (
                SELECT file_id
                FROM issues_files
                UNION
                SELECT file_id
                FROM volume_files
            )
            DELETE FROM files
            WHERE id NOT IN ids;
            """
        )
        return


class GeneralFilesDB:
    @staticmethod
    def fetch(volume_id: int) -> List[GeneralFileData]:
        result: List[GeneralFileData] = get_db().execute("""
            SELECT f.id, filepath, size, file_type
            FROM files f
            INNER JOIN volume_files vf
            ON f.id = vf.file_id
            WHERE volume_id = ?;
            """,
            (volume_id,)
        ).fetchalldict() # type: ignore

        return result

    @staticmethod
    def delete_linked_files(volume_id: int) -> None:
        get_db().execute(
            """
            DELETE FROM files
            WHERE id IN (
                SELECT DISTINCT file_id
                FROM volume_files
                WHERE volume_id = ?
            );
            """,
            (volume_id,)
        )
        return

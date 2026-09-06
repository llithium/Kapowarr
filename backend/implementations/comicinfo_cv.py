# -*- coding: utf-8 -*-

"""Resolve direct ComicVine references embedded in ComicInfo.xml."""

from asyncio import gather
from typing import Any, Dict, List, Set, Tuple

from backend.base.definitions import FilenameData
from backend.base.helpers import AsyncSession, batched
from backend.base.logging import LOGGER
from backend.implementations.comicinfo import ComicInfoData
from backend.implementations.comicvine import ComicVine


async def _fetch_issue_volume_ids(
    comicvine: ComicVine,
    issue_ids: Set[int]
) -> Dict[int, int]:
    """Resolve ComicVine issue IDs to their parent volume IDs in batches."""
    if not issue_ids:
        return {}

    result: Dict[int, int] = {}
    call_api = getattr(comicvine, '_ComicVine__call_api')

    async with AsyncSession() as session:
        for issue_batch in batched(sorted(issue_ids), 100):
            response = await call_api(
                session,
                '/issues',
                {
                    'field_list': 'id,volume',
                    'filter': 'id:' + '|'.join(map(str, issue_batch))
                },
                {'results': []}
            )

            for issue in response['results']:
                volume = issue.get('volume') or {}
                try:
                    issue_id = int(issue['id'])
                    volume_id = int(volume['id'])
                except (KeyError, TypeError, ValueError):
                    continue

                result[issue_id] = volume_id

    return result


async def match_comicinfo_ids(
    comicvine: ComicVine,
    file_groups: Dict[int, Dict[str, FilenameData]],
    comicinfo_metadata: Dict[str, ComicInfoData]
) -> Dict[int, Dict[str, Any]]:
    """Match import groups using direct ComicVine references from ComicInfo.

    A direct volume ID can be used immediately. ComicTagger commonly stores an
    issue URL such as ``.../4000-934000/`` in ``<Web>`` instead, so issue IDs are
    first resolved to their parent ComicVine volume. A group is only accepted
    when all direct references resolve consistently to one volume; otherwise the
    caller can fall back to Kapowarr's normal title-based matching.
    """
    direct_groups: Dict[int, Tuple[object, Set[int]]] = {}
    issue_ids_to_resolve: Set[int] = set()

    for group_number, files in file_groups.items():
        volume_ids = {
            metadata['comicvine_volume_id']
            for filepath, metadata in comicinfo_metadata.items()
            if filepath in files
            and metadata.get('comicvine_volume_id') is not None
        }
        issue_ids = {
            metadata['comicvine_issue_id']
            for filepath, metadata in comicinfo_metadata.items()
            if filepath in files
            and metadata.get('comicvine_issue_id') is not None
        }

        if len(volume_ids) > 1:
            LOGGER.warning(
                'Conflicting ComicVine volume IDs in ComicInfo.xml for group %s: %s',
                group_number,
                sorted(volume_ids)
            )
            continue

        volume_id = next(iter(volume_ids), None)
        if volume_id is None and issue_ids:
            issue_ids_to_resolve.update(issue_ids)

        if volume_id is not None or issue_ids:
            direct_groups[group_number] = (volume_id, issue_ids)

    if not direct_groups:
        return {}

    issue_volume_ids = await _fetch_issue_volume_ids(
        comicvine,
        issue_ids_to_resolve
    )

    resolved_groups: Dict[int, Tuple[int, str]] = {}
    for group_number, (direct_volume_id, issue_ids) in direct_groups.items():
        if isinstance(direct_volume_id, int):
            resolved_groups[group_number] = (
                direct_volume_id,
                'ComicVine volume ID from ComicInfo.xml'
            )
            continue

        if not issue_ids or any(
            issue_id not in issue_volume_ids
            for issue_id in issue_ids
        ):
            continue

        parent_volume_ids = {
            issue_volume_ids[issue_id]
            for issue_id in issue_ids
        }
        if len(parent_volume_ids) != 1:
            LOGGER.warning(
                'ComicInfo issue IDs for group %s resolve to multiple ComicVine volumes: %s',
                group_number,
                sorted(parent_volume_ids)
            )
            continue

        resolved_groups[group_number] = (
            next(iter(parent_volume_ids)),
            'ComicVine issue ID from ComicInfo.xml'
        )

    if not resolved_groups:
        return {}

    unique_volume_ids = sorted({
        volume_id
        for volume_id, _ in resolved_groups.values()
    })
    search_results = await gather(*(
        comicvine.search_volumes(
            f'4050-{volume_id}',
            allow_rate_limit_reached=True
        )
        for volume_id in unique_volume_ids
    ))
    volume_results = {
        volume_id: next((
            result
            for result in results
            if result['comicvine_id'] == volume_id
        ), None)
        for volume_id, results in zip(unique_volume_ids, search_results)
    }

    matches: Dict[int, Dict[str, Any]] = {}
    for group_number, (volume_id, reason) in resolved_groups.items():
        volume = volume_results.get(volume_id)
        if volume is None:
            continue

        matches[group_number] = {
            'id': volume['comicvine_id'],
            'title': f"{volume['title']} ({volume['year']})",
            'issue_count': volume['issue_count'],
            'link': volume['site_url'],
            'already_added': volume.get('already_added'),
            'match_source': 'comicinfo-id',
            'confidence': 100,
            'match_reason': reason,
            'direct_id': True
        }

    return matches

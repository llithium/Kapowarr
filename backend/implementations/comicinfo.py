# -*- coding: utf-8 -*-

"""Read and normalise ComicInfo.xml metadata from ZIP/CBZ comic archives."""

from os.path import basename, splitext
from typing import Dict, List, TypedDict, Union
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

from backend.base.definitions import FilenameData, SpecialVersion
from backend.base.file_extraction import extract_issue_number
from backend.base.helpers import normalise_string
from backend.base.logging import LOGGER


class ComicInfoData(TypedDict, total=False):
    """Useful ComicInfo.xml fields for identifying a comic during import."""

    series: str
    title: str
    issue_number: str
    volume: int
    issue_count: int
    year: int
    month: int
    day: int
    publisher: str
    format: str
    web: str
    gtin: str
    alternate_series: str


_ZIP_COMIC_EXTENSIONS = {'.cbz', '.zip'}


def _local_name(tag: str) -> str:
    """Return an XML tag without its optional namespace prefix."""
    return tag.rsplit('}', 1)[-1].lower()


def _normalise_text(value: Union[str, None]) -> Union[str, None]:
    if value is None:
        return None

    value = value.strip()
    return value or None


def _to_int(value: Union[str, None]) -> Union[int, None]:
    value = _normalise_text(value)
    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def _find_comicinfo_files(filenames: List[str]) -> List[str]:
    """Find ComicInfo.xml entries, preferring files closest to archive root."""
    matches = [
        filename
        for filename in filenames
        if basename(filename).lower() == 'comicinfo.xml'
    ]
    matches.sort(key=lambda f: (f.count('/'), len(f), f.lower()))
    return matches


def _parse_comicinfo(xml_data: bytes) -> Union[ComicInfoData, None]:
    try:
        root = ElementTree.fromstring(xml_data)
    except ElementTree.ParseError:
        return None

    values: Dict[str, str] = {}
    for child in root.iter():
        name = _local_name(child.tag)
        if name in values:
            continue

        value = _normalise_text(child.text)
        if value is not None:
            values[name] = value

    result: ComicInfoData = {}

    if 'series' in values:
        result['series'] = values['series']
    if 'title' in values:
        result['title'] = values['title']
    if 'number' in values:
        result['issue_number'] = values['number']
    if 'publisher' in values:
        result['publisher'] = values['publisher']
    if 'format' in values:
        result['format'] = values['format']
    if 'web' in values:
        result['web'] = values['web']
    if 'gtin' in values:
        result['gtin'] = values['gtin']
    if 'alternateseries' in values:
        result['alternate_series'] = values['alternateseries']

    volume = _to_int(values.get('volume'))
    if volume is not None:
        result['volume'] = volume

    issue_count = _to_int(values.get('count'))
    if issue_count is not None:
        result['issue_count'] = issue_count

    year = _to_int(values.get('year'))
    if year is not None:
        result['year'] = year

    month = _to_int(values.get('month'))
    if month is not None:
        result['month'] = month

    day = _to_int(values.get('day'))
    if day is not None:
        result['day'] = day

    return result or None


def read_comicinfo(filepath: str) -> Union[ComicInfoData, None]:
    """Read embedded ComicInfo.xml metadata from a ZIP-compatible comic.

    The reader is intentionally non-destructive. It only supports CBZ/ZIP in
    this first implementation; unsupported archives, missing metadata and
    malformed metadata all return ``None`` so callers can fall back to filename
    parsing.

    Args:
        filepath (str): Path to a comic archive.

    Returns:
        Union[ComicInfoData, None]: Parsed metadata, or ``None`` when no usable
            ComicInfo.xml can be read.
    """
    if splitext(filepath)[1].lower() not in _ZIP_COMIC_EXTENSIONS:
        return None

    try:
        with ZipFile(filepath, 'r') as archive:
            comicinfo_files = _find_comicinfo_files(archive.namelist())
            if not comicinfo_files:
                return None

            # If an archive contains multiple metadata files, use the one
            # closest to the archive root. This is the least surprising choice
            # for normal CBZ files while still supporting nested metadata.
            xml_data = archive.read(comicinfo_files[0])

    except (BadZipFile, KeyError, OSError):
        LOGGER.debug('Unable to read ComicInfo.xml from %s', filepath)
        return None

    return _parse_comicinfo(xml_data)


def _comicinfo_special_version(
    format_value: str
) -> Union[str, None, bool]:
    """Map a ComicInfo Format value to a Kapowarr special-version value.

    ``False`` means that the format is unknown and the filename-derived value
    should be kept. ``None`` means that the metadata explicitly describes a
    normal issue.
    """
    compact = ''.join(c for c in format_value.lower() if c.isalnum())

    if compact in ('oneshot', 'oneshotcomic'):
        return SpecialVersion.ONE_SHOT.value
    if compact in ('tpb', 'tradepaperback'):
        return SpecialVersion.TPB.value
    if compact in ('hc', 'hardcover'):
        return SpecialVersion.HARD_COVER.value
    if 'omnibus' in compact:
        return SpecialVersion.OMNIBUS.value
    if compact in ('comic', 'issue', 'annual'):
        return None

    return False


def comicinfo_to_filename_data(
    metadata: ComicInfoData,
    fallback: FilenameData,
    for_library_import: bool = False
) -> FilenameData:
    """Overlay ComicInfo metadata on filename-derived comic data.

    ComicInfo ``Year`` describes the individual issue's publication year. The
    library importer is trying to identify a ComicVine volume, whose ``year``
    describes the start of the overall series/volume. For that reason, the
    issue year is deliberately not used as a volume year during library import.

    Args:
        metadata (ComicInfoData): Parsed ComicInfo.xml metadata.
        fallback (FilenameData): Existing filename-derived values.
        for_library_import (bool, optional): Treat metadata year as an issue
            year rather than a volume year. Defaults to False.

    Returns:
        FilenameData: Values suitable for Kapowarr's existing matching code.
    """
    result = fallback.copy()

    series = metadata.get('series')
    if series:
        result['series'] = normalise_string(series)

    issue_number = metadata.get('issue_number')
    if issue_number:
        parsed_issue_number = extract_issue_number(issue_number)
        if parsed_issue_number is not None:
            result['issue_number'] = parsed_issue_number

    if 'volume' in metadata:
        result['volume_number'] = metadata['volume']
    elif for_library_import:
        # Filename extraction assumes Volume 1 when none is present. Tagged
        # libraries often omit the ComicVine volume number entirely, so that
        # assumption can make a good metadata match look worse than it is.
        result['volume_number'] = None

    if 'year' in metadata:
        result['year'] = None if for_library_import else metadata['year']

    format_value = metadata.get('format')
    if format_value:
        mapped_special_version = _comicinfo_special_version(format_value)
        if mapped_special_version is not False:
            result['special_version'] = mapped_special_version

        if 'annual' in format_value.lower():
            result['annual'] = True

    return result

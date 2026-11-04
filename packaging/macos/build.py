#!/usr/bin/env python3
"""Build an Apple Silicon app, ZIP, and drag-to-Applications disk image."""

import argparse
import hashlib
import importlib.metadata
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tomllib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'build' / 'macos'
DIST = ROOT / 'dist'
RAR_URL = 'https://www.rarlab.com/rar/rarmacos-arm-723.tar.gz'
RAR_SHA256 = '68b393c000758d477fde43c955ff7542f12f76f3f5e87cdda923152fc791bd4d'


def run(*args: str) -> None:
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-dmg', action='store_true')
    args = parser.parse_args()
    if sys.platform != 'darwin' or platform.machine() != 'arm64':
        parser.error('Build this app on an Apple Silicon Mac with Python 3.12+.')
    WORK.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(exist_ok=True)
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version']
    revision = subprocess.check_output(
        ['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT, text=True
    ).strip()
    identity = os.environ.get('MACOS_SIGNING_IDENTITY', '-')

    run(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--distpath', str(WORK / 'frozen'), '--workpath', str(WORK / 'pyinstaller'),
        str(ROOT / 'packaging' / 'macos' / 'server.spec'))
    app = DIST / 'Kapowarr.app'
    if app.exists():
        shutil.rmtree(app)
    contents = app / 'Contents'
    resources = contents / 'Resources'
    executable = contents / 'MacOS' / 'Kapowarr'
    executable.parent.mkdir(parents=True)
    shutil.copytree(WORK / 'frozen' / 'kapowarr-server', resources / 'server', symlinks=True)
    licenses = resources / 'Licenses'
    licenses.mkdir()
    shutil.copy2(ROOT / 'LICENSE', licenses / 'Kapowarr.txt')
    python_license = next(path for path in (
        Path(sys.base_prefix) / 'LICENSE.txt',
        Path(sysconfig.get_path('stdlib')) / 'LICENSE.txt',
    ) if path.is_file())
    shutil.copy2(python_license, licenses / 'Python.txt')
    # Retain license and notice files supplied by dependency wheels.
    for distribution in importlib.metadata.distributions():
        for file in distribution.files or ():
            if not file.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE')):
                continue
            source = distribution.locate_file(file)
            if source.is_file():
                destination = licenses / distribution.metadata['Name'] / str(file).replace('/', '_')
                destination.parent.mkdir(exist_ok=True)
                shutil.copy2(source, destination)
    # Only UnRAR is redistributed, never the proprietary RAR compressor.
    archive = WORK / 'rarmacos-arm-723.tar.gz'
    if not archive.exists():
        urllib.request.urlretrieve(RAR_URL, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != RAR_SHA256:
        raise RuntimeError(f'UnRAR download checksum mismatch: {archive}')
    with tarfile.open(archive) as tar:
        for source, destination in (
            ('rar/unrar', resources / 'server' / '_internal' / 'backend' / 'lib' / 'unrar'),
            ('rar/license.txt', licenses / 'RAR-UnRAR.txt'),
            ('rar/readme.txt', licenses / 'RAR-UnRAR-readme.txt'),
        ):
            member = tar.extractfile(source)
            if member is None:
                raise RuntimeError(f'Missing UnRAR component: {source}')
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(member.read())
    unrar = resources / 'server' / '_internal' / 'backend' / 'lib' / 'unrar'
    unrar.chmod(0o755)
    run('xcrun', 'swiftc', '-O', '-target', 'arm64-apple-macos15.0',
        str(ROOT / 'packaging' / 'macos' / 'Launcher.swift'), '-o', str(executable))

    icon = WORK / 'icon.png'
    run('xcrun', 'swift', str(ROOT / 'packaging' / 'macos' / 'Icon.swift'),
        str(ROOT / 'frontend' / 'static' / 'img' / 'favicon.svg'), str(icon))
    iconset = WORK / 'Kapowarr.iconset'
    iconset.mkdir(exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        for scale in (1, 2):
            name = f'icon_{size}x{size}{"@2x" if scale == 2 else ""}.png'
            run('sips', '-z', str(size * scale), str(size * scale),
                str(icon), '--out', str(iconset / name))
    run('iconutil', '-c', 'icns', str(iconset), '-o', str(resources / 'Kapowarr.icns'))

    info = {
        'CFBundleIdentifier': 'io.github.llithium.Kapowarr',
        'CFBundleName': 'Kapowarr',
        'CFBundleDisplayName': 'Kapowarr',
        'CFBundleExecutable': 'Kapowarr',
        'CFBundlePackageType': 'APPL',
        'CFBundleIconFile': 'Kapowarr.icns',
        'CFBundleShortVersionString': version,
        'CFBundleVersion': os.environ.get('GITHUB_RUN_NUMBER', '1'),
        'KapowarrRevision': revision,
        'LSMinimumSystemVersion': '15.0',
        'LSUIElement': True,
        'NSHighResolutionCapable': True,
        'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True},
        'NSDocumentsFolderUsageDescription': 'Kapowarr manages comics in folders you add to your library.',
        'NSDownloadsFolderUsageDescription': 'Kapowarr imports downloaded comics into your library.',
        'NSDesktopFolderUsageDescription': 'Kapowarr accesses comics in folders you add to your library.',
        'NSHumanReadableCopyright': 'Kapowarr contributors. GNU GPL v3.',
    }
    (contents / 'Info.plist').write_bytes(plistlib.dumps(info))
    signing_options = [] if identity == '-' else ['--options', 'runtime', '--timestamp']
    # PyInstaller signs its libraries; re-sign with the requested identity,
    # including the additional native launcher and UnRAR, from the inside out.
    signed = set()
    for binary in sorted(contents.rglob('*')):
        if binary.is_symlink() or not binary.is_file():
            continue
        with binary.open('rb') as stream:
            magic = stream.read(4)
        if magic not in (b'\xcf\xfa\xed\xfe', b'\xce\xfa\xed\xfe', b'\xca\xfe\xba\xbe'):
            continue
        if binary.resolve() not in signed:
            run('codesign', '--force', '--sign', identity, *signing_options, str(binary))
            signed.add(binary.resolve())
    # Sign framework containers after their executable and resources.
    for framework in sorted(contents.rglob('*.framework'), reverse=True):
        run('codesign', '--force', '--sign', identity, *signing_options, str(framework))
    run('codesign', '--force', '--sign', identity, *signing_options, str(app))
    run('codesign', '--verify', '--deep', '--strict', str(app))

    name = f'Kapowarr-{version}-macOS-arm64'
    zip_path = DIST / f'{name}.zip'
    if zip_path.exists():
        zip_path.unlink()
    run('ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(app), str(zip_path))
    outputs = [zip_path]
    if not args.skip_dmg:
        staging = WORK / 'dmg'
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir()
        shutil.copytree(app, staging / app.name, symlinks=True)
        (staging / 'Applications').symlink_to('/Applications')
        dmg = DIST / f'{name}.dmg'
        if dmg.exists():
            dmg.unlink()
        run('hdiutil', 'create', '-volname', 'Kapowarr', '-srcfolder', str(staging),
            '-ov', '-format', 'UDZO', str(dmg))
        profile = os.environ.get('MACOS_NOTARY_PROFILE')
        if profile:
            if identity == '-':
                raise RuntimeError('Notarization requires MACOS_SIGNING_IDENTITY.')
            run('xcrun', 'notarytool', 'submit', str(dmg), '--keychain-profile', profile, '--wait')
            run('xcrun', 'stapler', 'staple', str(dmg))
        outputs.append(dmg)
    (DIST / 'SHA256SUMS.txt').write_text(''.join(
        f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n' for path in outputs
    ))
    print(f'Built {app} ({version}, {revision})', flush=True)


if __name__ == '__main__':
    main()

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


root = Path(SPECPATH).resolve().parents[1]
datas = [
    (str(root / 'frontend' / 'templates'), 'frontend/templates'),
    (str(root / 'frontend' / 'static'), 'frontend/static'),
    (str(root / 'pyproject.toml'), '.'),
]
# Registration discovers implementations by filename, including in a bundle.
for package in ('backend', 'frontend'):
    datas += [
        (str(source), str(source.parent.relative_to(root)))
        for source in (root / package).rglob('*.py')
    ]

analysis = Analysis(
    [str(root / 'packaging' / 'macos' / 'server.py')],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=(
        ['Kapowarr', 'engineio.async_drivers.threading']
        + collect_submodules('backend')
        + collect_submodules('frontend')
    ),
    excludes=['tkinter', 'pytest', 'unittest'],
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz, analysis.scripts, [],
    exclude_binaries=True,
    name='kapowarr-server',
    console=True,
    codesign_identity=None,
)
collection = COLLECT(
    exe, analysis.binaries, analysis.datas,
    name='kapowarr-server',
)

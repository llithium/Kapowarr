# macOS app

The self-contained Kapowarr app runs on Apple Silicon Macs with macOS 15 or
newer. Python, Python dependencies, web assets, and UnRAR are included.

## Install and use

1. Download the Apple Silicon DMG from this fork's
   [releases](https://github.com/llithium/Kapowarr/releases).
2. Open the DMG and drag **Kapowarr** to **Applications**.
3. Quit any copy started by `Kapowarr.command`, then open **Kapowarr.app**.

Kapowarr starts its local server and opens the web interface in your default
browser. Its books icon in the menu bar provides **Open Kapowarr**, **View Logs**,
**Download Updates**, and **Quit Kapowarr**. Closing the last Kapowarr browser tab
quits the app and stops its server and worker processes after a five-second
grace period. Reloading or moving between pages keeps the app running. If you
have several Kapowarr tabs open, it runs until the last one closes. You can also
use **Quit Kapowarr** to stop it directly.

Opening the app again opens the interface for the running instance. The launcher
rejects a second server using the same data folder and reports a port conflict
if another service is already listening on Kapowarr's saved port.

The server listens on `127.0.0.1` and uses the port and URL base saved in its
settings. It is accessible from this Mac.

## Library data and updates

The app uses `~/Library/Application Support/Kapowarr/Kapowarr.db`, including an
existing database at that location. Your comic folders stay where they are.
Logs are in `~/Library/Logs/Kapowarr`. A new installation puts temporary downloads
in `~/Library/Application Support/Kapowarr/temp_downloads`; an existing
installation keeps its configured download folder.

To update, quit Kapowarr and replace the app with a newer build. Your database,
backups, settings, and comics are outside the app. The app does not run Git or
install Python packages at startup.

UnRAR is bundled for extracting RAR/CBR files and converting them to ZIP/CBZ.
Creating new RAR/CBR files requires a separate RAR installation. The app looks
for it in `/opt/homebrew/bin`, `/usr/local/bin`, and the system command folders.

## Signing

The default builds are ad-hoc signed and are not notarized by Apple. macOS may
block a downloaded copy. After attempting to open it, use **System Settings →
Privacy & Security → Open Anyway** if macOS offers that option for Kapowarr.
This applies to downloaded releases; a locally built app normally opens directly.

## Build locally

Building requires Apple's Command Line Tools and Python 3.12 or newer on an
Apple Silicon Mac. Using the finished app does not require either.

```sh
python3.12 -m venv build/macos-venv
build/macos-venv/bin/python -m pip install -r packaging/macos/requirements.txt
build/macos-venv/bin/python packaging/macos/build.py
build/macos-venv/bin/python packaging/macos/smoke_test.py dist/Kapowarr.app
build/macos-venv/bin/python packaging/macos/browser_lifetime_test.py dist/Kapowarr.app
```

The build produces `dist/Kapowarr.app`, an app ZIP, a drag-to-Applications DMG,
and `dist/SHA256SUMS.txt`. It downloads a pinned, checksum-verified archive from
RARLAB and includes only the redistributable UnRAR executable and its notices.
The proprietary RAR compressor is not included.

The smoke test uses a temporary database, a separate local port, and a command
path without Homebrew or installed Python. It checks the bundled interpreter,
spawned workers, client registration, web assets, archive extraction, database
export, server restart, duplicate-launch protection, and shutdown. The browser
lifetime check also verifies multiple tabs, navigation, and cleanup of the
entire server process group when the last tab closes.

For a Developer ID build, set `MACOS_SIGNING_IDENTITY` to an identity in your
keychain. Set `MACOS_NOTARY_PROFILE` to a `notarytool` keychain profile to submit
and staple the DMG during the build. These credentials are optional and are not
stored in the repository.

## Automated builds and releases

The **macOS app** GitHub Actions workflow builds and tests the app on pull
requests, pushes to `main`, and manual runs. Each successful push to `main`
publishes installers on the releases page with a new `mac-vVERSION.BUILD` tag.
Pull requests and manual runs provide the ZIP and DMG in the run's
**Kapowarr-macOS-arm64** artifact.

To publish a separately named release, push a new tag beginning with `mac-v`,
for example `mac-v1.3.2.1`. Each tag must be new. The workflow runs the
backend tests, builds the app, checks the app lifecycle and code signature,
then publishes the installers and checksums. Other Kapowarr release tags and
the Docker workflow are independent of the Mac release tags.

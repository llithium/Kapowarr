# Testing the ComicInfo Library Import fork

This repository includes an isolated Docker Compose setup so the importer can be tested without touching an existing Kapowarr database or the production comics folder.

## Safety model

The test stack uses:

- container name `kapowarr-comicinfo-test`
- host port `9001`
- its own database volume
- its own logs volume
- its own temporary-download volume
- a dedicated `./test-data/comics` folder mounted as `/comics-1`

It does **not** mount your normal Kapowarr database or your production comics directory.

## 1. Check out the repository

```powershell
git clone https://github.com/llithium/Kapowarr.git
cd Kapowarr
git switch main
```

If the repository is already cloned:

```powershell
git fetch origin
git switch main
git pull
```

## 2. Create test folders

From the repository root in PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path .\test-data\comics\_import | Out-Null
```

Copy a **small number of duplicate/test copies** of ComicTagger-tagged CBZ files into:

```text
test-data\comics\_import\
```

Do not use your only copy of a comic for the first test. Library Import may move files when a match is already present, and `Import and Rename` can rename them.

Good first test cases:

```text
Batman (2020) Issue 085.cbz
Batman - The Killing Joke (1988) Issue 001.cbz
Cory Doctorow's Futuristic Tales of the Here and Now (2007) Issue 001.cbz
```

The files should contain ComicTagger-generated `ComicInfo.xml` metadata.

## 3. Build and start the test container

```powershell
docker compose -f docker-compose.test.yml up -d --build
```

Open:

```text
http://localhost:9001
```

Your normal Kapowarr instance can continue running on port 9000.

## 4. Initial Kapowarr setup

In the test instance:

1. Add your ComicVine API key.
2. Add `/comics-1/` as the root folder.
3. Keep the media-management naming settings the same as your production instance if you want to compare behavior.

The test database is intentionally empty, so production settings are not copied automatically.

## 5. Test new-volume import

Go to **Library Import** and scan `/comics-1/_import`.

For tagged CBZ files, the proposal table should show:

- `ComicInfo.xml` under **Metadata**
- the embedded series/issue/year information in the Metadata tooltip
- either `ComicVine` or `Existing library` under **Match info**

For the first pass, use **Import**, not **Import and Rename**. This preserves the ComicTagger filename.

Verify that the comic is added and that its issue is marked downloaded.

## 6. Test adding an issue to an existing volume

This is the important regression case.

1. Import/add a volume normally in the test instance so it already exists in its database.
2. Put another tagged issue from that same run into `/comics-1/_import`.
3. Run Library Import again.

Expected result:

- **Match info** should say `Existing library` with a confidence score.
- The file should be moved into the existing volume folder when imported.
- Normal **Import** should preserve the ComicTagger filename.
- The issue should become downloaded without manually moving the file and refreshing.

## 7. Test a special version with an issue number

Use a tagged one-shot such as:

```text
Batman - The Killing Joke (1988) Issue 001.cbz
```

with ComicInfo metadata similar to:

```xml
<Format>One-Shot</Format>
<Number>1</Number>
```

Expected result: Kapowarr can keep both the One-Shot classification and issue number 1. You should not have to remove `Issue 001` from the filename.

## 8. Inspect logs

```powershell
docker compose -f docker-compose.test.yml logs -f kapowarr-test
```

Useful messages include existing-library match decisions and the ComicInfo fallback used for otherwise-unmatched issue files.

## 9. Stop or reset the test instance

Stop it while keeping the test database:

```powershell
docker compose -f docker-compose.test.yml down
```

Completely reset the test database and other test volumes:

```powershell
docker compose -f docker-compose.test.yml down -v
```

The files in `./test-data/comics` are bind-mounted and are **not** deleted by `down -v`.

## Current limitations

- Embedded ComicInfo reading supports CBZ/ZIP and CBR/RAR. On macOS, RAR reading uses `bsdtar`; supported platforms also use the bundled RAR reader as a fallback.
- Archives without readable ComicInfo metadata fall back to filename parsing.
- Automated tests cover parsing, caching, and representative import flows. Use the Docker walkthrough above to verify behavior with your own tagged archives.

# Download Engine Updates

The Windows GUI runs the official standalone `yt-dlp.exe`. Its bundled EJS
scripts update with it; rebuilding the GUI is no longer needed for routine
YouTube extractor updates.

- The app checks the official nightly release on startup, at most once per local day.
- "Update Engine" checks immediately, including after a failed automatic check.
- On HTTP 403 the app checks for an update and retries the operation once.
- Offline checks keep the installed engine. Each replacement verifies the official
  SHA-256 checksum and version before activation, and retains the prior engine.
- An update waits until an active download finishes. Separate app instances share
  a filesystem lock so the running engine is not replaced.

Components and update state are stored under:

```text
%LOCALAPPDATA%\YoutubeVideoDownloader\components\
    yt-dlp.exe
    yt-dlp.previous.exe
    update.json
```

The application contains a seed engine for first launch. Node.js 22 or newer is
still required. FFmpeg stays in `ffmpeg\bin` beside the GUI executable (or on
PATH). Node.js and FFmpeg are not automatically upgraded by this feature.

## Build

From the project directory:

```powershell
python -m pip install -r requirements.txt
python -m pip install pyinstaller
python -c "from download_engine import ComponentManager; print(ComponentManager(directory='components').update(force=True))"
python -m PyInstaller --noconfirm YouTubeDownloader.spec
```

The seed is downloaded from `yt-dlp/yt-dlp-nightly-builds` on GitHub and verified
against that release's `SHA2-256SUMS`. Distribute `dist\YouTubeDownloader.exe`
together with the existing `ffmpeg` directory. Do not distribute the update lock
or per-user update state.

## Verify

```powershell
python -m unittest test_download_engine -v
```

# YouTube Video Downloader

A Windows Python application with a bilingual GUI to download YouTube videos.

## Features

- **GUI Interface**: Easy to use graphical interface.
- **Resolution Selection**: Choose from available video resolutions (1080p, 720p, etc.).
- **Custom Download Path**: Save videos to your preferred location.
- **High Quality Support**: Downloads best video and audio streams (requires FFmpeg).
- **Automatic Engine Updates**: Checks official yt-dlp nightly releases at most once per day, with an Update Engine button for immediate checks.
- **Safe Updates**: Verifies SHA-256 and version before replacement, retains the previous engine, and keeps the installed version when offline.
- **403 Recovery**: Checks for an engine update and retries once after an HTTP 403 error.
- **Download Controls**: Pause, resume, stop, and browse download history.

## Prerequisites

- Windows 10 or newer (64-bit)
- Python 3.9 or newer (source builds only; not needed for the packaged GUI)
- [Node.js](https://nodejs.org/) 22 or newer
- [FFmpeg](https://ffmpeg.org/download.html) (Required for merging high-quality video and audio)

## Installation

1. Clone the repository or download the source code.
2. Install the required dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```

## Usage

Run the GUI application:

```bash
python gui.py
```

1. Paste the YouTube video URL.
2. Click **Analyze**.
3. Select your desired resolution.
4. Choose a download folder (defaults to your Downloads folder).
5. Click **Start Download**.

The app downloads and runs the official standalone `yt-dlp.exe`, including its
EJS scripts. Routine engine updates do not require rebuilding the GUI. The engine
is stored in `%LOCALAPPDATA%\YoutubeVideoDownloader\components`, so updates do
not require administrator permissions. Updates wait for active downloads to finish.

Use **Update Engine** (Chinese: **立即更新**) to check immediately. Node.js and
FFmpeg remain separately installed; the app does not upgrade them automatically.

## Build and Test

See [AUTO_UPDATE.md](AUTO_UPDATE.md) for component setup, PyInstaller build
instructions, and update behavior. The initial engine is embedded in the GUI
as a seed so a fresh install can start without downloading it again.

```powershell
python -m unittest test_download_engine -v
```

## Note on FFmpeg

Separate video and audio streams require **FFmpeg** for merging at any resolution.
Place `ffmpeg\bin` beside the GUI executable or add FFmpeg to PATH.

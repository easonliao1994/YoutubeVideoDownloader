# YouTube Video Downloader

A simple Python application with a user-friendly GUI to download YouTube videos.

## Features

- **GUI Interface**: Easy to use graphical interface.
- **Resolution Selection**: Choose from available video resolutions (1080p, 720p, etc.).
- **Custom Download Path**: Save videos to your preferred location.
- **High Quality Support**: Downloads best video and audio streams (requires FFmpeg).

## Prerequisites

- Python 3.x
- [FFmpeg](https://ffmpeg.org/download.html) (Required for merging high-quality video and audio)

## Installation

1. Clone the repository or download the source code.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
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

## Note on FFmpeg

To download videos in 1080p or higher with audio, **FFmpeg** must be installed and added to your system's PATH. Without FFmpeg, you may be limited to 720p or video-only files.

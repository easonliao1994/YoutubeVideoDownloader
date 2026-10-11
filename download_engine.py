"""Independently updatable official yt-dlp executable and GUI adapter."""

from collections import deque
from contextlib import contextmanager
from datetime import date
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request

import psutil


RELEASE_API = 'https://api.github.com/repos/yt-dlp/yt-dlp-nightly-builds/releases/latest'
ASSET_PREFIX = 'https://github.com/yt-dlp/yt-dlp-nightly-builds/releases/download/'
PROGRESS_PREFIX = '__YTDLP_PROGRESS__'
FILE_PREFIX = '__YTDLP_FILE__'
_LOCK = threading.RLock()
_CREATE_NO_WINDOW = getattr(subprocess, 'CREATE_NO_WINDOW', 0)


class EngineError(RuntimeError):
    pass


class DownloadStopped(EngineError):
    pass


class ComponentManager:
    def __init__(self, directory=None, seed=None):
        default = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'YoutubeVideoDownloader' / 'components'
        self.directory = Path(directory or default)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.executable = self.directory / 'yt-dlp.exe'
        self.backup = self.directory / 'yt-dlp.previous.exe'
        self.state_file = self.directory / 'update.json'
        resource_dir = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
        self.seed = Path(seed) if seed else resource_dir / 'components' / 'yt-dlp.exe'

    @contextmanager
    def locked(self):
        # The shared lock also prevents another app instance updating a running engine.
        with _LOCK:
            with open(self.directory / 'engine.lock', 'a+b') as handle:
                if handle.tell() == 0:
                    handle.write(b'0')
                    handle.flush()
                if os.name == 'nt':
                    import msvcrt
                    while True:
                        try:
                            handle.seek(0)
                            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                            break
                        except OSError:
                            time.sleep(0.1)
                try:
                    yield
                finally:
                    if os.name == 'nt':
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)

    def version(self, path=None):
        result = subprocess.run(
            [str(path or self.executable), '--version'], capture_output=True,
            text=True, encoding='utf-8', errors='replace', timeout=30,
            creationflags=_CREATE_NO_WINDOW,
        )
        version = result.stdout.strip()
        if result.returncode or not re.fullmatch(r'\d{4}\.\d{2}\.\d{2}(?:\.[\w.]+)?', version):
            raise EngineError('The download engine failed its version check.')
        return version

    def _read_state(self):
        try:
            return json.loads(self.state_file.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def _write_state(self, state):
        pending = self.state_file.with_suffix('.tmp')
        pending.write_text(json.dumps(state), encoding='utf-8')
        os.replace(pending, self.state_file)

    def _fetch(self, url):
        request = urllib.request.Request(url, headers={'User-Agent': 'YoutubeVideoDownloader', 'Accept': 'application/vnd.github+json'})
        return urllib.request.urlopen(request, timeout=20)

    def _release(self):
        with self._fetch(RELEASE_API) as response:
            return json.load(response)

    def _download_candidate(self, release, destination):
        assets = {asset['name']: asset['browser_download_url'] for asset in release['assets']}
        urls = [assets['yt-dlp.exe'], assets['SHA2-256SUMS']]
        if any(not url.startswith(ASSET_PREFIX) for url in urls):
            raise EngineError('Unexpected component download source.')
        with self._fetch(urls[1]) as response:
            sums = response.read().decode('utf-8')
        expected = next((line.split()[0] for line in sums.splitlines()
                         if len(line.split()) == 2 and line.split()[1].lstrip('*') == 'yt-dlp.exe'), None)
        if not expected or not re.fullmatch('[a-fA-F0-9]{64}', expected):
            raise EngineError('Official SHA-256 checksum was not found.')
        digest = hashlib.sha256()
        with self._fetch(urls[0]) as response, open(destination, 'wb') as output:
            while block := response.read(1024 * 1024):
                output.write(block)
                digest.update(block)
        if digest.hexdigest().lower() != expected.lower():
            raise EngineError('Component checksum did not match; existing version kept.')

    def _ensure(self):
        if self.executable.exists():
            return
        if self.seed.is_file():
            shutil.copy2(self.seed, self.executable)
        elif self.backup.is_file():
            shutil.copy2(self.backup, self.executable)

    def update(self, force=False):
        with self.locked():
            self._ensure()
            state = self._read_state()
            today = date.today().isoformat()
            if not force and self.executable.exists() and state.get('last_check') == today:
                return {'status': 'skipped', 'version': self.version(), 'error': state.get('error', '')}
            candidate = None
            try:
                release = self._release()
                installed = self.version() if self.executable.exists() else None
                if installed == release['tag_name']:
                    result = {'status': 'current', 'version': installed, 'error': ''}
                else:
                    with tempfile.NamedTemporaryFile(dir=self.directory, suffix='.exe', delete=False) as file:
                        candidate = Path(file.name)
                    self._download_candidate(release, candidate)
                    version = self.version(candidate)
                    if version != release['tag_name']:
                        raise EngineError('Downloaded component version did not match the release.')
                    if self.executable.exists():
                        shutil.copy2(self.executable, self.backup)
                    os.replace(candidate, self.executable)
                    candidate = None
                    try:
                        self.version()
                    except Exception:
                        if self.backup.exists():
                            os.replace(self.backup, self.executable)
                        raise
                    result = {'status': 'updated', 'version': version, 'error': ''}
                self._write_state(dict(result, last_check=today))
                return result
            except Exception as error:
                if not self.executable.exists():
                    raise EngineError(f'Could not install the download engine: {error}') from error
                result = {'status': 'failed', 'version': self.version(), 'error': str(error)}
                self._write_state(dict(result, last_check=today))
                return result
            finally:
                if candidate is not None:
                    candidate.unlink(missing_ok=True)


def _stop_tree(process):
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
    except psutil.NoSuchProcess:
        return
    for child in reversed(children):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    try:
        parent.kill()
    except psutil.NoSuchProcess:
        pass


class DownloadEngine:
    def __init__(self, manager):
        self.manager = manager
        self._process = None
        self._closed = threading.Event()
        self._node = None

    def cancel(self):
        self._closed.set()
        process = self._process
        if process is not None and process.poll() is None:
            _stop_tree(process)

    def _base_args(self):
        node = shutil.which('node')
        if not node:
            node_path = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'nodejs' / 'node.exe'
            node = str(node_path) if node_path.is_file() else None
        if not node:
            raise EngineError('Node.js is missing. Install Node.js 22 or newer and restart the application.')
        if self._node != node:
            result = subprocess.run([node, '--version'], capture_output=True, text=True,
                                    timeout=10, creationflags=_CREATE_NO_WINDOW)
            match = re.match(r'v(\d+)\.', result.stdout.strip())
            if result.returncode or not match or int(match[1]) < 22:
                raise EngineError('Node.js 22 or newer is required. Update Node.js and restart the application.')
            self._node = node
        args = ['--ignore-config', '--no-playlist', '--no-colors', '--encoding', 'utf-8',
                '--js-runtimes', f'node:{node}', '--retries', '3', '--socket-timeout', '20',
                '--abort-on-unavailable-fragments']
        base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
        ffmpeg = base / 'ffmpeg' / 'bin'
        if (ffmpeg / 'ffmpeg.exe').is_file():
            args += ['--ffmpeg-location', str(ffmpeg)]
        return args

    def _run(self, args, on_line=None, stopped=None, paused=None):
        with self.manager.locked():
            if self._closed.is_set():
                raise DownloadStopped('Application closed')
            self.manager._ensure()
            command = [str(self.manager.executable), *self._base_args(), *args]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       text=True, encoding='utf-8', errors='replace',
                                       creationflags=_CREATE_NO_WINDOW)
            self._process = process
            lines = queue.Queue()

            def read_output():
                try:
                    for line in process.stdout:
                        lines.put(line.rstrip())
                finally:
                    lines.put(None)

            reader = threading.Thread(target=read_output, daemon=True)
            reader.start()
            output = [] if on_line is None else deque(maxlen=30)
            suspended = []
            try:
                while True:
                    if self._closed.is_set() or (stopped and stopped()):
                        raise DownloadStopped('Stopped by user')
                    wants_pause = paused and paused()
                    if wants_pause and not suspended and process.poll() is None:
                        parent = psutil.Process(process.pid)
                        suspended = parent.children(recursive=True) + [parent]
                        for item in reversed(suspended):
                            try:
                                item.suspend()
                            except psutil.NoSuchProcess:
                                pass
                    if suspended and not wants_pause:
                        for item in suspended:
                            try:
                                item.resume()
                            except psutil.NoSuchProcess:
                                pass
                        suspended = []
                    try:
                        line = lines.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    if line is None:
                        break
                    output.append(line)
                    if on_line:
                        on_line(line)
                code = process.wait()
                if code:
                    raise EngineError('\n'.join(output)[-6000:])
                return '\n'.join(output)
            finally:
                if process.poll() is None:
                    _stop_tree(process)
                process.wait()
                reader.join(timeout=5)
                process.stdout.close()
                self._process = None

    def extract_info(self, url):
        self.manager.update()
        output = self._retry(lambda: self._run(['--dump-single-json', '--skip-download', '--', url]))
        for line in reversed(output.splitlines()):
            if line.startswith('{'):
                return json.loads(line)
        raise EngineError('The download engine returned no video information.')

    def _retry(self, action):
        try:
            return action()
        except EngineError as error:
            if isinstance(error, DownloadStopped) or not re.search(r'HTTP (?:Error )?403|403: Forbidden', str(error), re.I):
                raise
            self.manager.update(force=True)
            return action()

    def download(self, url, format_str, output_template, progress_hook=None, stopped=None, paused=None):
        self.manager.update()
        final_paths = []

        def on_line(line):
            if line.startswith(PROGRESS_PREFIX):
                data = json.loads(line[len(PROGRESS_PREFIX):])
                if progress_hook:
                    progress_hook(data)
            elif line.startswith(FILE_PREFIX):
                final_paths.append(json.loads(line[len(FILE_PREFIX):]))

        args = ['--no-simulate', '--newline', '--progress', '--progress-delta', '0.5',
                '--progress-template', f'download:{PROGRESS_PREFIX}%(progress)j',
                '--print', f'after_move:{FILE_PREFIX}%(filepath)j',
                '-f', format_str, '-o', output_template, '--', url]
        self._retry(lambda: self._run(args, on_line, stopped, paused))
        if not final_paths:
            raise EngineError('Download finished without a final output file.')
        return final_paths[-1]

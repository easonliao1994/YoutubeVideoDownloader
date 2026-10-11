import hashlib
import io
import tempfile
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from download_engine import ComponentManager, DownloadEngine, DownloadStopped, EngineError, ASSET_PREFIX


OLD = '2026.03.17'
NEW = '2026.10.10.233141'


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.manager = ComponentManager(self.temp.name, seed=Path(self.temp.name) / 'absent.exe')
        self.manager.executable.write_text(OLD)
        self.manager.version = lambda path=None: Path(path or self.manager.executable).read_text()
        self.manager._release = Mock(return_value={'tag_name': NEW})
        self.manager._download_candidate = lambda release, path: path.write_text(NEW)

    def test_update_keeps_backup_and_checks_only_once_per_day(self):
        self.assertEqual(self.manager.update()['status'], 'updated')
        self.assertEqual(self.manager.backup.read_text(), OLD)
        self.assertEqual(self.manager.executable.read_text(), NEW)
        self.assertEqual(self.manager.update()['status'], 'skipped')
        self.manager._release.assert_called_once()
        self.assertEqual(self.manager.update(force=True)['status'], 'current')
        self.assertEqual(self.manager._release.call_count, 2)

    def test_offline_update_keeps_existing_engine_and_records_attempt(self):
        self.manager._release.side_effect = OSError('offline')
        self.assertEqual(self.manager.update()['status'], 'failed')
        self.assertEqual(self.manager.executable.read_text(), OLD)
        self.assertEqual(self.manager.update()['status'], 'skipped')
        self.manager._release.assert_called_once()

    def test_wrong_version_does_not_replace_existing_engine(self):
        self.manager._download_candidate = lambda release, path: path.write_text('wrong')
        self.assertEqual(self.manager.update()['status'], 'failed')
        self.assertEqual(self.manager.executable.read_text(), OLD)
        self.assertEqual(list(self.manager.directory.glob('tmp*.exe')), [])

    def test_failed_post_install_check_restores_backup(self):
        def version(path=None):
            data = Path(path or self.manager.executable).read_text()
            if path is None and data == NEW:
                raise EngineError('unusable after install')
            return data
        self.manager.version = version
        self.assertEqual(self.manager.update()['status'], 'failed')
        self.assertEqual(self.manager.executable.read_text(), OLD)

    def test_checksum_mismatch_rejects_candidate(self):
        release = {'assets': [
            {'name': 'yt-dlp.exe', 'browser_download_url': ASSET_PREFIX + NEW + '/yt-dlp.exe'},
            {'name': 'SHA2-256SUMS', 'browser_download_url': ASSET_PREFIX + NEW + '/SHA2-256SUMS'},
        ]}
        sums = (hashlib.sha256(b'expected').hexdigest() + '  yt-dlp.exe\n').encode()
        self.manager._fetch = Mock(side_effect=[io.BytesIO(sums), io.BytesIO(b'corrupted')])
        with self.assertRaisesRegex(EngineError, 'checksum'):
            ComponentManager._download_candidate(self.manager, release, self.manager.directory / 'candidate.exe')
        self.assertEqual(self.manager.executable.read_text(), OLD)


class RetryTests(unittest.TestCase):
    def test_403_updates_and_retries_once(self):
        manager = Mock()
        engine = DownloadEngine(manager)
        action = Mock(side_effect=[EngineError('HTTP Error 403: Forbidden'), 'ok'])
        self.assertEqual(engine._retry(action), 'ok')
        manager.update.assert_called_once_with(force=True)
        self.assertEqual(action.call_count, 2)

    def test_second_403_is_reported_without_infinite_retry(self):
        manager = Mock()
        action = Mock(side_effect=EngineError('HTTP Error 403: Forbidden'))
        with self.assertRaises(EngineError):
            DownloadEngine(manager)._retry(action)
        self.assertEqual(action.call_count, 2)

    def test_stop_or_unrelated_error_does_not_update(self):
        for error in (DownloadStopped('Stopped'), EngineError('disk full')):
            with self.subTest(error=error):
                manager = Mock()
                with self.assertRaises(type(error)):
                    DownloadEngine(manager)._retry(Mock(side_effect=error))
                manager.update.assert_not_called()


class ProcessControlTests(unittest.TestCase):
    def test_pause_resume_and_stop_external_process(self):
        with tempfile.TemporaryDirectory() as folder:
            manager = ComponentManager(folder)
            manager.executable = Path(sys.executable)
            engine = DownloadEngine(manager)
            engine._base_args = lambda: []
            pause = threading.Event()
            stop = threading.Event()
            received = []
            errors = []
            code = 'import time\nwhile True:\n print("tick", flush=True)\n time.sleep(0.05)'

            def run():
                try:
                    engine._run(['-u', '-c', code], received.append, stop.is_set, pause.is_set)
                except Exception as error:
                    errors.append(error)

            worker = threading.Thread(target=run)
            worker.start()
            try:
                deadline = time.monotonic() + 10
                while len(received) < 3 and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertGreaterEqual(len(received), 3)
                pause.set()
                time.sleep(0.4)
                count = len(received)
                time.sleep(0.3)
                self.assertEqual(len(received), count)
                pause.clear()
                deadline = time.monotonic() + 5
                while len(received) <= count and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertGreater(len(received), count)
                stop.set()
                worker.join(timeout=5)
                self.assertFalse(worker.is_alive())
                self.assertIsInstance(errors[0], DownloadStopped)
                self.assertIsNone(engine._process)
            finally:
                stop.set()
                engine.cancel()
                worker.join(timeout=5)


if __name__ == '__main__':
    unittest.main()

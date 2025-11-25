import unittest
import tempfile
import io
from pathlib import Path
from datetime import datetime

import drive.poller as poller_mod
from drive.models import PDFFile


class FakeExec:
    def execute(self):
        return {"id": "fake"}


class FakeFiles:
    def __init__(self):
        self.updated = None

    def get_media(self, fileId):
        # Return a dummy request object; our FakeDownloader ignores it
        return object()

    def update(self, fileId, body):
        self.updated = (fileId, body)
        return FakeExec()


class FakeService:
    def __init__(self):
        self.files_resource = FakeFiles()

    def files(self):
        return self.files_resource


class FakeDownloader:
    def __init__(self, fh, request, chunksize=None):
        self.fh = fh
        self._done = False

    def next_chunk(self):
        if not self._done:
            self.fh.write(b"%PDF-1.4\n%%EOF")
            self._done = True
            return None, True
        return None, True


class TestDrivePollerDownloadAndSanitize(unittest.TestCase):
    def test_sanitizer_basic(self):
        s = poller_mod.DrivePoller._sanitize_filename("עוש ארבעה חודשים.pdf")
        self.assertTrue(s.endswith('.pdf'))
        self.assertNotIn('ע', s)

    def test_download_uses_sanitized_local_name_only(self):
        # Create a DrivePoller without running __init__ (avoid network/auth)
        p = object.__new__(poller_mod.DrivePoller)

        tmp = tempfile.TemporaryDirectory()
        p.temp_dir = Path(tmp.name)
        p.temp_dir.mkdir(parents=True, exist_ok=True)

        # Fake service and monkeypatch downloader
        fake_service = FakeService()
        p.service = fake_service

        # Monkeypatch module-level downloader class
        original_downloader = poller_mod.MediaIoBaseDownload
        poller_mod.MediaIoBaseDownload = FakeDownloader

        try:
            pdf = PDFFile(id='file123', name='עוש ארבעה חודשים.pdf', size=1234, created_time=datetime.now())

            local_path = p.download_pdf(pdf, 'cust1')

            # remote update should NOT have been attempted (we no longer rename remote files)
            self.assertIsNone(fake_service.files_resource.updated)

            # local_path should equal sanitized name and file created
            self.assertTrue(local_path.exists())
            self.assertNotIn('ע', local_path.name)

        finally:
            poller_mod.MediaIoBaseDownload = original_downloader
            tmp.cleanup()

import io
import tempfile
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from django.core.exceptions import SuspiciousFileOperation, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image
from pypdf import PdfWriter

from apps.test_support import Stage1DataMixin
from .models import File
from .private_files import private_path
from .uploads import validate_uploaded_files
from .views import handle_uploaded_files


def pdf_upload(name="report.pdf", active=False):
    output = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    if active:
        writer.add_js("app.alert('test');")
    writer.write(output)
    return SimpleUploadedFile(name, output.getvalue(), content_type="text/html")


def office_upload(ext, active=False):
    output = io.BytesIO()
    main = "word/document.xml" if ext == ".docx" else "xl/workbook.xml"
    root = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>'
            if ext == ".docx" else '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"/>')
    content_type = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
                    if ext == ".docx" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml")
    with ZipFile(output, "w") as archive:
        archive.writestr("[Content_Types].xml", f'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/{main}" ContentType="{content_type}"/></Types>')
        archive.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')
        archive.writestr(main, root)
        if active:
            archive.writestr("word/vbaProject.bin", b"macro")
    return SimpleUploadedFile("document" + ext, output.getvalue())


class ContentTests(SimpleTestCase):
    def test_valid_pdf_and_ooxml_ignore_untrusted_mime(self):
        for file in (pdf_upload(), office_upload(".docx"), office_upload(".xlsx")):
            with self.subTest(name=file.name):
                validate_uploaded_files([file])
                self.assertEqual(file.tell(), 0)

    def test_valid_images(self):
        for fmt, ext in (("PNG", ".png"), ("JPEG", ".jpg"), ("JPEG", ".jpeg")):
            output = io.BytesIO()
            Image.new("RGB", (2, 2)).save(output, fmt)
            validate_uploaded_files([SimpleUploadedFile("photo" + ext, output.getvalue())])

    def test_html_and_signatures_without_valid_structure_rejected_for_every_extension(self):
        for ext in ("pdf", "doc", "docx", "xls", "xlsx", "jpg", "jpeg", "png"):
            with self.subTest(extension=ext):
                with self.assertRaises(ValidationError):
                    validate_uploaded_files([SimpleUploadedFile("spoof." + ext, b"<html><script>alert(1)</script></html>")])
        with self.assertRaises(ValidationError):
            validate_uploaded_files([SimpleUploadedFile("spoof.pdf", b"%PDF-1.7\n%%EOF")])

    def test_active_pdf_and_office_rejected(self):
        for file in (pdf_upload(active=True), office_upload(".docx", active=True)):
            with self.assertRaises(ValidationError):
                validate_uploaded_files([file])

    def test_wrong_office_type_and_broken_zip_rejected(self):
        file = office_upload(".xlsx")
        file.name = "spoof.docx"
        for value in (file, SimpleUploadedFile("bad.docx", b"PK\x03\x04broken")):
            with self.assertRaises(ValidationError):
                validate_uploaded_files([value])

    def test_limits(self):
        for files in ([pdf_upload() for _ in range(6)],
                      [SimpleUploadedFile("big.pdf", b"x" * (10 * 1024 * 1024 + 1))],
                      [SimpleUploadedFile("empty.pdf", b"")],
                      [SimpleUploadedFile("script.html", b"html")]):
            with self.assertRaises(ValidationError):
                validate_uploaded_files(files)


class DownloadTests(Stage1DataMixin, TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.temp.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        Path(self.temp.name, "legacy").mkdir()
        Path(self.temp.name, "legacy", "report.pdf").write_bytes(pdf_upload().read())
        self.file = File.objects.create(order=self.order, uploaded_by_user=self.committee,
            original_filename='C:\\untrusted\\report\r\n.pdf', file_path='legacy\\report.pdf')
        self.url = reverse("prescriptions:file_download", args=[self.file.pk])

    def test_anonymous_rejected(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_authorized_download_has_safe_headers_and_legacy_path(self):
        for user in (self.committee, self.director, self.system):
            self.client.force_login(user)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
            self.assertIn("attachment;", response["Content-Disposition"])
            self.assertNotIn("\r", response["Content-Disposition"])
            self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF-"))

    def test_other_institution_unknown_role_and_unassigned_rejected(self):
        self.file.order = self.other_order
        self.file.save()
        for user, expected in ((self.director, 404), (self.unknown, 403), (self.unassigned, 403)):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url).status_code, expected)

    @override_settings(DEBUG=True)
    def test_direct_media_not_public_even_in_debug(self):
        self.assertEqual(self.client.get("/media/legacy/report.pdf").status_code, 404)

    def test_path_traversal_denied(self):
        for value in ("../outside", "C:\\outside", "/outside", "..\\outside"):
            with self.assertRaises(SuspiciousFileOperation):
                private_path(value)

    def test_file_metadata_failure_rolls_back_and_cleans_written_files(self):
        before = File.objects.count()
        with self.assertRaises(IntegrityError), patch("apps.prescriptions.views.File.objects.create", side_effect=IntegrityError("injected")):
            with transaction.atomic():
                handle_uploaded_files(self.order, [pdf_upload()], self.committee)
        self.assertEqual(File.objects.count(), before)
        self.assertEqual(len(list(Path(self.temp.name).rglob("*.pdf"))), 1)

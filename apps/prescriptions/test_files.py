import io
import struct
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


def ole_upload(ext):
    # Minimal real CFB container with regular 4096-byte Office streams.
    free, end, fat_sector = 0xffffffff, 0xfffffffe, 0xfffffffd
    header = bytearray(512)
    header[:8] = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1'
    struct.pack_into('<HHHHH', header, 24, 62, 3, 0xfffe, 9, 6)
    struct.pack_into('<IIIIIIIII', header, 40, 0, 1, 0, 0, 4096, end, 0, end, 0)
    struct.pack_into('<109I', header, 76, 1, *([free]*108))
    def entry(name, kind, first, size, child=free, right=free):
        row = bytearray(128)
        encoded = (name+'\0').encode('utf-16le')
        row[:len(encoded)] = encoded
        struct.pack_into('<HBBIII', row, 64, len(encoded), kind, 1, free, right, child)
        struct.pack_into('<IQ', row, 116, first, size)
        return row
    if ext == '.doc':
        word = bytearray(4096)
        word[:4] = b'\xec\xa5\xc1\x00'
        streams = [('WordDocument', bytes(word)), ('0Table', bytes(4096))]
    else:
        book = struct.pack('<HHHHI', 0x0809, 8, 0x0600, 5, 0)
        book += struct.pack('<HH', 0x003c, 4076) + bytes(4076) + struct.pack('<HH', 0x000a, 0)
        streams = [('Workbook', book)]
    directory = entry('Root Entry', 5, end, 0, child=1)
    fat = [end, fat_sector]
    payload = b''
    for index, (name, content) in enumerate(streams):
        start = 2 + 8*index
        directory += entry(name, 2, start, len(content), right=index+2 if index+1 < len(streams) else free)
        fat.extend([*range(start+1, start+8), end])
        payload += content
    directory += bytes(512-len(directory))
    fat += [free]*(128-len(fat))
    return SimpleUploadedFile('legacy'+ext, bytes(header)+directory+struct.pack('<128I', *fat)+payload)


class ContentTests(SimpleTestCase):
    def test_valid_legacy_doc_and_xls_structures(self):
        for ext in ('.doc', '.xls'):
            validate_uploaded_files([ole_upload(ext)])
        disguised = ole_upload('.doc')
        disguised.name = 'spoof.xls'
        with self.assertRaises(ValidationError):
            validate_uploaded_files([disguised])

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
        for user in (self.committee, self.director, self.system, self.admin):
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

"""Bounded content checks without trusting the browser MIME or libmagic DLLs."""
import io
import struct
import warnings
from pathlib import PurePosixPath
from zipfile import ZipFile

import olefile
from defusedxml import ElementTree as ET
from django.core.exceptions import ValidationError
from PIL import Image
from pypdf import PdfReader
from pypdf.generic import IndirectObject

MAX_FILE_SIZE = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".jpg", ".jpeg", ".png"}


def _pdf(data):
    if not data.startswith(b"%PDF-") or not data.rstrip().endswith(b"%%EOF"):
        raise ValueError("PDF signature")
    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted or not 0 < len(reader.pages) <= 5000:
        raise ValueError("PDF encryption/size")
    blocked = {"/JS", "/JavaScript", "/OpenAction", "/AA", "/Launch", "/EmbeddedFiles", "/RichMedia", "/XFA"}
    pending, visited = [reader.trailer], set()
    budget = 100000
    while pending:
        budget -= 1
        if budget < 0:
            raise ValueError("PDF complexity")
        obj = pending.pop()
        if isinstance(obj, IndirectObject):
            key = (obj.idnum, obj.generation)
            if key in visited:
                continue
            visited.add(key)
            obj = obj.get_object()
        if isinstance(obj, dict):
            if blocked.intersection(obj):
                raise ValueError("Active PDF content")
            pending.extend(obj.values())
        elif isinstance(obj, (list, tuple)):
            pending.extend(obj)


def _ooxml(data, ext):
    with ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        names = {entry.filename for entry in entries}
        if len(entries) > 1000 or len(names) != len(entries) or sum(e.file_size for e in entries) > 40 * 1024 * 1024:
            raise ValueError("ZIP size")
        for entry in entries:
            name = entry.filename
            if PurePosixPath(name).is_absolute() or ".." in name.split("/") or "\\" in name or entry.flag_bits & 1:
                raise ValueError("ZIP path/encryption")
            if entry.file_size > MAX_FILE_SIZE or entry.file_size > max(1, entry.compress_size) * 200:
                raise ValueError("ZIP compression")
            if any(part in name.lower() for part in ("vbaproject", "embeddings/", "activex/", "externallinks/")):
                raise ValueError("Active Office content")
        main = "word/document.xml" if ext == ".docx" else "xl/workbook.xml"
        if not {"[Content_Types].xml", "_rels/.rels", main}.issubset(names):
            raise ValueError("Office structure")
        content = ET.fromstring(archive.read("[Content_Types].xml"))
        expected = ("application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
                    if ext == ".docx" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml")
        if not any(n.get("PartName") == "/" + main and n.get("ContentType") == expected for n in content):
            raise ValueError("Office content type")
        expected_root = ("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}document" if ext == ".docx"
                         else "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}workbook")
        if ET.fromstring(archive.read(main)).tag != expected_root:
            raise ValueError("Office root")
        for name in names:
            if name.endswith((".xml", ".rels")):
                xml = ET.fromstring(archive.read(name))
                if name.endswith(".rels") and any(rel.get("TargetMode") == "External" and not rel.get("Type", "").endswith("/hyperlink") for rel in xml):
                    raise ValueError("External Office relationship")
        if archive.testzip() is not None:
            raise ValueError("Office CRC")


def _ole(data, ext):
    if not data.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        raise ValueError("OLE signature")
    with olefile.OleFileIO(io.BytesIO(data), raise_defects=olefile.DEFECT_INCORRECT) as doc:
        paths = ["/".join(path).lower() for path in doc.listdir()]
        if any(any(token in path for token in ("vba", "macros", "objpool", "encryptedpackage")) for path in paths):
            raise ValueError("Active/encrypted Office content")
        if ext == ".doc":
            fib = doc.openstream("WordDocument").read(32)
            if len(fib) < 32 or fib[:2] != b"\xec\xa5":
                raise ValueError("Word FIB")
            flags = struct.unpack_from("<H", fib, 10)[0]
            if flags & 0x0100 or not doc.exists("1Table" if flags & 0x0200 else "0Table"):
                raise ValueError("Word table/encryption")
        else:
            workbook = doc.openstream("Workbook" if doc.exists("Workbook") else "Book").read()
            if len(workbook) < 12 or workbook[:2] != b"\x09\x08" or workbook[4:6] not in (b"\x00\x05", b"\x00\x06"):
                raise ValueError("Excel BIFF")
            offset, found_eof = 0, False
            while offset + 4 <= len(workbook):
                record, size = struct.unpack_from("<HH", workbook, offset)
                offset += 4
                if offset + size > len(workbook) or record == 0x002F:
                    raise ValueError("Excel record/encryption")
                found_eof |= record == 0x000A
                offset += size
            if not found_eof or offset != len(workbook):
                raise ValueError("Excel structure")


def validate_uploaded_files(files):
    if len(files) > 5:
        raise ValidationError("Можно загрузить не более 5 файлов.")
    for uploaded in files:
        ext = PurePosixPath(uploaded.name.replace("\\", "/")).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError("Недопустимый формат. Разрешены PDF, DOC, DOCX, XLS, XLSX, JPG, JPEG, PNG.")
        if uploaded.size > MAX_FILE_SIZE:
            raise ValidationError("Размер каждого файла не должен превышать 10 МБ.")
        try:
            uploaded.seek(0)
            data = uploaded.read(MAX_FILE_SIZE + 1)
            if not data or len(data) > MAX_FILE_SIZE:
                raise ValueError("File size")
            if ext in {".png", ".jpg", ".jpeg"}:
                expected = "PNG" if ext == ".png" else "JPEG"
                if (expected == "PNG" and not data.endswith(b"\x00\x00\x00\x00IEND\xaeB`\x82")) or (expected == "JPEG" and not data.endswith(b"\xff\xd9")):
                    raise ValueError("Image ending")
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(io.BytesIO(data), formats=[expected]) as img:
                        if img.width * img.height > 25_000_000:
                            raise ValueError("Image dimensions")
                        img.verify()
                    with Image.open(io.BytesIO(data), formats=[expected]) as img:
                        img.load()
            elif ext == ".pdf":
                _pdf(data)
            elif ext in {".docx", ".xlsx"}:
                _ooxml(data, ext)
            else:
                _ole(data, ext)
        except Exception as error:
            raise ValidationError(
                f'Файл «{uploaded.name}» повреждён, содержит активное содержимое или не соответствует формату. '
                'Используйте документ без макросов, вложенных объектов и пароля.'
            ) from error
        finally:
            uploaded.seek(0)

from pathlib import Path

from django.core.exceptions import ValidationError


ALLOWED_COMPANY_DOCUMENT_EXTENSIONS = {'.pdf', '.docx'}
ALLOWED_COMPANY_LOGO_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.svg', '.webp'}
COMPANY_DOCUMENT_MAX_UPLOAD_SIZE = 15 * 1024 * 1024
COMPANY_LOGO_MAX_UPLOAD_SIZE = 2 * 1024 * 1024


def _validate_upload(upload, *, allowed_extensions, max_size, invalid_extension_message, size_message):
    if not upload:
        return upload

    ext = Path(upload.name).suffix.lower()
    if ext not in allowed_extensions:
        raise ValidationError(invalid_extension_message)

    if upload.size > max_size:
        raise ValidationError(size_message)

    return upload


def validate_company_document_upload(upload):
    return _validate_upload(
        upload,
        allowed_extensions=ALLOWED_COMPANY_DOCUMENT_EXTENSIONS,
        max_size=COMPANY_DOCUMENT_MAX_UPLOAD_SIZE,
        invalid_extension_message='Sono accettati solo file PDF o DOCX.',
        size_message='Il file non può superare 15 MB.',
    )


def validate_company_logo_upload(upload):
    return _validate_upload(
        upload,
        allowed_extensions=ALLOWED_COMPANY_LOGO_EXTENSIONS,
        max_size=COMPANY_LOGO_MAX_UPLOAD_SIZE,
        invalid_extension_message='Il logo deve essere in formato PNG, JPG, JPEG, SVG o WEBP.',
        size_message='Il logo non può superare 2 MB.',
    )

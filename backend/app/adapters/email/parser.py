from email import policy
from email.parser import BytesParser

from bs4 import BeautifulSoup
from app.adapters.models import ParsedAttachment, ParsedSourceDocument, ParsedSourcePart


def _html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text("\n", strip=True)


def _collect_body_parts(message):
    plain_text_parts = []
    html_parts = []
    for part in message.walk():
        disposition = (part.get_content_disposition() or "").lower()
        if disposition == "attachment":
            continue
        content_type = part.get_content_type()
        try:
            payload = part.get_content()
        except Exception:
            payload = None
        if not payload:
            continue
        if content_type == "text/plain" and isinstance(payload, str):
            text = payload.strip()
            if text:
                plain_text_parts.append(text)
        elif content_type == "text/html" and isinstance(payload, str):
            text = _html_to_text(payload).strip()
            if text:
                html_parts.append(text)
    return plain_text_parts, html_parts


def parse_eml_bytes(content: bytes, file_name: str) -> ParsedSourceDocument:
    message = BytesParser(policy=policy.default).parsebytes(content)
    attachments = []
    parts = []

    header_lines = []
    for key in ("From", "To", "Cc", "Bcc", "Date", "Subject", "Message-ID"):
        value = message.get(key)
        if value:
            header_lines.append(f"{key}: {value}")
    header_text = "\n".join(header_lines).strip()
    if header_text:
        parts.append(
            ParsedSourcePart(
                part_type="email_header",
                part_index=0,
                title=message.get("Subject") or file_name,
                locator_json={"section": "headers"},
                content_text=header_text,
                provenance_json={"parser": "email+bs4", "file_name": file_name},
            )
        )

    plain_text_parts, html_parts = _collect_body_parts(message)
    body_text = "\n\n".join(plain_text_parts).strip()
    body_format = "text/plain"
    if not body_text and html_parts:
        body_text = "\n\n".join(html_parts).strip()
        body_format = "text/html_fallback"
    if body_text:
        parts.append(
            ParsedSourcePart(
                part_type="email_body",
                part_index=1,
                title="Email Body",
                locator_json={"section": "body", "body_format": body_format},
                content_text=body_text,
                provenance_json={"parser": "email+bs4", "file_name": file_name},
            )
        )

    for attachment in message.iter_attachments():
        payload = attachment.get_payload(decode=True) or b""
        attachments.append(
            ParsedAttachment(
                file_name=attachment.get_filename() or "attachment.bin",
                content_type=attachment.get_content_type(),
                size_bytes=len(payload),
                content_disposition=attachment.get_content_disposition(),
                content_id=attachment.get("Content-ID"),
            )
        )

    warnings = []
    if not parts:
        warnings.append("No EML header/body text found.")

    return ParsedSourceDocument(
        source_type="eml",
        title=message.get("Subject") or file_name,
        metadata={
            "file_name": file_name,
            "from": message.get("From"),
            "to": message.get("To"),
            "subject": message.get("Subject"),
            "attachment_count": len(attachments),
            "body_format_used": body_format if body_text else None,
        },
        parts=parts,
        attachments=attachments,
        warnings=warnings,
    )

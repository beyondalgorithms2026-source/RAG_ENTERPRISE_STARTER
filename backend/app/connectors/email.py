from dataclasses import dataclass, field
from typing import Any

from app.adapters.models import ParsedAttachment, ParsedSourceDocument, ParsedSourcePart


@dataclass
class EmailAttachmentRecord:
    file_name: str
    content_type: str | None = None
    content_bytes: bytes = b""
    content_id: str | None = None


@dataclass
class EmailMessageRecord:
    subject: str
    body_text: str
    from_email: str | None = None
    to_email: str | None = None
    cc_email: str | None = None
    sent_at: str | None = None
    message_id: str | None = None
    mailbox: str | None = None
    folder: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    attachments: list[EmailAttachmentRecord] = field(default_factory=list)


def parsed_document_from_email_record(record: EmailMessageRecord) -> ParsedSourceDocument:
    header_fields = {
        "From": record.from_email,
        "To": record.to_email,
        "Cc": record.cc_email,
        "Date": record.sent_at,
        "Subject": record.subject,
        "Message-ID": record.message_id,
        "Mailbox": record.mailbox,
        "Folder": record.folder,
    }
    header_text = "\n".join(
        f"{key}: {value}" for key, value in header_fields.items() if value
    ).strip()
    parts: list[ParsedSourcePart] = []
    if header_text:
        parts.append(
            ParsedSourcePart(
                part_type="email_header",
                part_index=0,
                title=record.subject,
                locator_json={
                    "section": "headers",
                    "mailbox": record.mailbox,
                    "folder": record.folder,
                },
                content_text=header_text,
                provenance_json={"parser": "email_connector", "message_id": record.message_id},
            )
        )
    if record.body_text.strip():
        parts.append(
            ParsedSourcePart(
                part_type="email_body",
                part_index=1,
                title="Email Body",
                locator_json={
                    "section": "body",
                    "mailbox": record.mailbox,
                    "folder": record.folder,
                },
                content_text=record.body_text.strip(),
                provenance_json={"parser": "email_connector", "message_id": record.message_id},
            )
        )

    attachments = [
        ParsedAttachment(
            file_name=attachment.file_name,
            content_type=attachment.content_type,
            size_bytes=len(attachment.content_bytes),
            content_id=attachment.content_id,
            content_disposition="attachment",
            content_bytes=attachment.content_bytes,
        )
        for attachment in record.attachments
    ]

    metadata = {
        "source_kind": "mailbox_archive",
        "from": record.from_email,
        "to": record.to_email,
        "subject": record.subject,
        "message_id": record.message_id,
        "mailbox": record.mailbox,
        "folder": record.folder,
        "attachment_count": len(attachments),
        **record.metadata,
    }
    return ParsedSourceDocument(
        source_type="email_message",
        title=record.subject,
        metadata=metadata,
        parts=parts,
        attachments=attachments,
        warnings=[] if parts else ["No email header/body text found."],
    )

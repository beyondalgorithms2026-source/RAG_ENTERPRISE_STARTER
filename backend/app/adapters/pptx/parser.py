from io import BytesIO

from pptx import Presentation
from app.adapters.models import ParsedSourceDocument, ParsedSourcePart


def _shape_texts(slide) -> list[str]:
    texts = []
    for shape in slide.shapes:
        if not hasattr(shape, "text"):
            continue
        value = (shape.text or "").strip()
        if value:
            texts.append(value)
    return texts


def _notes_text(slide) -> str:
    notes_slide = getattr(slide, "notes_slide", None)
    if notes_slide is None:
        return ""
    texts = []
    for shape in notes_slide.shapes:
        if not hasattr(shape, "text"):
            continue
        value = (shape.text or "").strip()
        if value:
            texts.append(value)
    return "\n".join(texts).strip()


def parse_pptx_bytes(content: bytes, file_name: str) -> ParsedSourceDocument:
    warnings = []
    presentation = Presentation(BytesIO(content))
    parts = []
    for slide_index, slide in enumerate(presentation.slides):
        slide_number = slide_index + 1
        slide_texts = _shape_texts(slide)
        notes_text = _notes_text(slide)
        if not slide_texts and not notes_text:
            continue
        body_text = "\n".join(slide_texts).strip()
        combined_text = body_text
        if notes_text:
            combined_text = f"{body_text}\n\nSpeaker Notes:\n{notes_text}".strip()
        title_shape = slide.shapes.title
        title = (title_shape.text or "").strip() if title_shape is not None and title_shape.text else None
        if not title:
            title = slide_texts[0].splitlines()[0] if slide_texts else f"Slide {slide_number}"
        parts.append(
            ParsedSourcePart(
                part_type="slide",
                part_index=slide_index,
                title=title,
                locator_json={"slide": slide_number},
                content_text=combined_text,
                provenance_json={"parser": "python-pptx", "file_name": file_name, "has_notes": bool(notes_text)},
            )
        )

    if not parts:
        warnings.append("No PPTX slide text found.")

    return ParsedSourceDocument(
        source_type="pptx",
        title=file_name,
        metadata={"file_name": file_name, "slide_count": len(presentation.slides)},
        parts=parts,
        warnings=warnings,
    )

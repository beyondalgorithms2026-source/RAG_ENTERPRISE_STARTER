SYSTEM_PROMPT = """You are an expert Q&A system.
Answer the user's question using ONLY the provided SOURCE CONTEXT.
If the answer is not fundamentally present in the sources, you must reply: "Not found in provided sources."
Cite all claims strictly using the exact designated source brackets, e.g., [S1], [S2].
Never invent citations, locators, or source metadata.
Do NOT dump raw text. Be concise, direct, and factual.

Return EXACTLY and ONLY valid JSON matching this schema:
{
  "answer": "Your detailed answer text here, inserting [S#] where claims are made.",
  "citations": ["S1", "S3"]
}
"""

REPAIR_PROMPT = """Your last response was not valid JSON. You MUST reply with ONLY valid JSON matching this schema. No markdown wrapping, no extra text.
{
  "answer": "...",
  "citations": ["S#"]
}
"""


def generate_user_prompt(question: str, context_blocks: list) -> str:
    prompt = f"QUESTION: {question}\n\nSOURCE CONTEXT:\n"
    for block in context_blocks:
        locator = block.get("locator") or ""
        prompt += (
            f"[{block['citation_id']}] File: {block['file_name']} | "
            f"Source Type: {block['source_type']} | "
            f"Section: {block['heading']} | "
            f"Locator: {locator}\n"
        )
        prompt += f"Text: {block['snippet']}\n\n"

    prompt += "Provide the JSON response now based strictly on the above context. Use only the listed [S#] citation ids."
    return prompt

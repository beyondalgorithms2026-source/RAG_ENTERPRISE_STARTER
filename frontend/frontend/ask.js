function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function setMessage(container, tone, text) {
    if (!text) {
        container.innerHTML = "";
        return;
    }
    container.innerHTML = `<div class="message message-${tone}">${escapeHtml(text)}</div>`;
}

function citationCard(citation) {
    const locator = citation.locator ? `<span>Locator: ${escapeHtml(citation.locator)}</span>` : "<span>Locator: n/a</span>";
    return `
        <article class="citation-card">
            <div class="citation-head">
                <div>
                    <h4 class="citation-title">[${escapeHtml(citation.citation_id)}] ${escapeHtml(citation.file_name)}</h4>
                    <div class="citation-meta">
                        <span class="source-chip">${escapeHtml(citation.source_type)}</span>
                        ${locator}
                        <span>Chunk: ${escapeHtml(citation.chunk_id)}</span>
                        <span>Source Part: ${escapeHtml(citation.source_part_id ?? "n/a")}</span>
                    </div>
                </div>
                <span class="muted-text">${escapeHtml(citation.heading)}</span>
            </div>
            <p class="citation-snippet">${escapeHtml(citation.snippet)}</p>
        </article>
    `;
}

export function initAsk({ apiBase, setHealth }) {
    const questionInput = document.getElementById("ask-question");
    const modeInput = document.getElementById("ask-mode");
    const sourceTypeInput = document.getElementById("ask-source-type");
    const kChunksInput = document.getElementById("ask-k-chunks");
    const dryRunInput = document.getElementById("ask-dry-run");
    const askSubmit = document.getElementById("ask-submit");
    const askMeta = document.getElementById("ask-meta");
    const askMessage = document.getElementById("ask-message");
    const answerState = document.getElementById("answer-state");
    const answerBody = document.getElementById("answer-body");
    const answerMetrics = document.getElementById("answer-metrics");
    const answerText = document.getElementById("answer-text");
    const answerDebug = document.getElementById("answer-debug");
    const citationsWrap = document.getElementById("citations-wrap");
    const citationsList = document.getElementById("citations-list");

    function resetAnswerView() {
        answerBody.classList.add("hidden");
        citationsWrap.classList.add("hidden");
        answerMetrics.textContent = "";
        answerText.textContent = "";
        answerDebug.textContent = "";
        answerDebug.classList.add("hidden");
        citationsList.innerHTML = "";
    }

    function currentFilters() {
        const sourceType = sourceTypeInput.value || null;
        return sourceType ? { source_type: sourceType } : null;
    }

    async function submitAsk() {
        const question = questionInput.value.trim();
        if (!question) {
            setMessage(askMessage, "warning", "Enter a question before calling /ask.");
            return;
        }

        askSubmit.disabled = true;
        askMeta.textContent = "Submitting question...";
        setMessage(askMessage, "", "");
        answerState.textContent = "Waiting for grounded answer...";
        resetAnswerView();

        try {
            const payload = {
                question,
                k_chunks: Number(kChunksInput.value || 6),
                filters: currentFilters(),
                mode: modeInput.value || null,
                dry_run: dryRunInput.checked,
            };

            const response = await fetch(`${apiBase}/ask`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const result = await response.json().catch(() => ({}));

            if (!response.ok) {
                const detail = result?.detail;
                const message = typeof detail === "string"
                    ? detail
                    : detail?.message || detail?.error || `Ask failed: ${response.status}`;
                throw new Error(message);
            }

            setHealth(true, "Backend connected");
            askMeta.textContent = `Mode sent: ${payload.mode || "default"} | dry_run=${payload.dry_run}`;
            answerState.textContent = result.answer || "Dry run complete.";
            answerBody.classList.remove("hidden");
            answerMetrics.textContent = `Latency ${result.latency_ms} ms | Used chunks ${result.used_chunks_count}`;
            answerText.textContent = result.answer || "";

            if (result.debug_info) {
                answerDebug.classList.remove("hidden");
                answerDebug.textContent = JSON.stringify(result.debug_info, null, 2);
            }

            if (Array.isArray(result.citations) && result.citations.length > 0) {
                citationsWrap.classList.remove("hidden");
                citationsList.innerHTML = result.citations.map(citationCard).join("");
            } else if (!result.debug_info) {
                citationsWrap.classList.remove("hidden");
                citationsList.innerHTML = "<p class=\"muted-text\">No citations returned.</p>";
            }
        } catch (error) {
            setHealth(false, "Ask request failed");
            setMessage(askMessage, "error", error.message);
            answerState.textContent = "Unable to complete the ask request.";
        } finally {
            askSubmit.disabled = false;
        }
    }

    askSubmit.addEventListener("click", submitAsk);
}

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

function formatModeLabel(value) {
    const normalized = String(value || "hybrid").trim().toLowerCase();
    if (normalized === "vector") {
        return "Semantic";
    }
    if (normalized === "graph_hybrid") {
        return "Graph Hybrid";
    }
    return normalized
        .split(/[_\s-]+/)
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

function answerParagraphs(text) {
    return String(text || "")
        .split(/\n\s*\n/)
        .map((part) => part.trim())
        .filter(Boolean)
        .map((part) => `<p class="answer-paragraph">${escapeHtml(part)}</p>`)
        .join("");
}

function metricPills(result) {
    const items = [
        `Latency ${escapeHtml(result.latency_ms ?? "n/a")} ms`,
        `Used Chunks ${escapeHtml(result.used_chunks_count ?? 0)}`,
    ];
    if (result.mode) {
        items.push(`Mode ${escapeHtml(formatModeLabel(result.mode))}`);
    }
    return items.map((item) => `<span class="metric-pill">${item}</span>`).join("");
}

function splitTerms(value) {
    return String(value || "")
        .split(/[,\n]/)
        .map((part) => part.trim())
        .filter(Boolean);
}

function refStrip(citations) {
    return citations.map((citation, index) => `
        <button type="button" class="ref-pill" data-citation-target="${escapeHtml(citation.citation_id)}">
            REF ${String(index + 1).padStart(2, "0")}
        </button>
    `).join("");
}

function citationCard(citation) {
    const locator = citation.locator ? `<span>Locator: ${escapeHtml(citation.locator)}</span>` : "<span>Locator: n/a</span>";
    return `
        <article class="citation-card" data-citation-id="${escapeHtml(citation.citation_id)}">
            <div class="citation-head">
                <div>
                    <span class="citation-ref">REF ${escapeHtml(citation.citation_id)}</span>
                    <h4 class="citation-title">${escapeHtml(citation.file_name)}</h4>
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
    const deepResearchInput = document.getElementById("ask-deep-research");
    const customQueryInput = document.getElementById("ask-custom-query");
    const anchorTermsInput = document.getElementById("ask-anchor-terms");
    const exactPhraseInput = document.getElementById("ask-exact-phrase");
    const forceRareKeywordScanInput = document.getElementById("ask-force-rare-keyword-scan");
    const expandNeighborsInput = document.getElementById("ask-expand-neighbors");
    const askSubmit = document.getElementById("ask-submit");
    const askMeta = document.getElementById("ask-meta");
    const askMessage = document.getElementById("ask-message");
    const deepResearchWarning = document.getElementById("deep-research-warning");
    const answerState = document.getElementById("answer-state");
    const answerBody = document.getElementById("answer-body");
    const answerMetrics = document.getElementById("answer-metrics");
    const answerText = document.getElementById("answer-text");
    const answerDebug = document.getElementById("answer-debug");
    const answerRefStrip = document.getElementById("answer-ref-strip");
    const citationsWrap = document.getElementById("citations-wrap");
    const citationsList = document.getElementById("citations-list");
    const analysisModeBadge = document.getElementById("analysis-mode-badge");
    const analysisCurrentInquiry = document.getElementById("analysis-current-inquiry");
    const previewPlaceholder = document.getElementById("preview-placeholder");
    const recentInquiriesList = document.getElementById("recent-inquiries-list");
    const modeGuide = document.getElementById("mode-guide");
    const deepResearchPanel = document.getElementById("deep-research-panel");
    const askProgress = document.getElementById("ask-progress");
    const askProgressLabel = document.getElementById("ask-progress-label");
    const askProgressValue = document.getElementById("ask-progress-value");
    const askProgressFill = document.getElementById("ask-progress-fill");
    const RECENTS_KEY = "rag-master-recent-inquiries";
    const ASK_STAGES = [
        { progress: 12, label: "Receiving question" },
        { progress: 28, label: "Searching sources" },
        { progress: 46, label: "Merging evidence" },
        { progress: 68, label: "Preparing answer context" },
        { progress: 84, label: "Generating grounded answer" },
    ];
    let askProgressTimer = null;

    function loadRecentInquiries() {
        try {
            const raw = window.localStorage.getItem(RECENTS_KEY);
            const items = JSON.parse(raw || "[]");
            return Array.isArray(items) ? items : [];
        } catch (_error) {
            return [];
        }
    }

    function saveRecentInquiry(question, mode) {
        const next = [
            {
                question,
                mode: formatModeLabel(mode),
                saved_at: new Date().toISOString(),
            },
            ...loadRecentInquiries().filter((item) => item.question !== question),
        ].slice(0, 4);

        try {
            window.localStorage.setItem(RECENTS_KEY, JSON.stringify(next));
        } catch (_error) {
            // Ignore storage failures.
        }
        renderRecentInquiries();
    }

    function renderRecentInquiries() {
        if (!recentInquiriesList) {
            return;
        }
        const items = loadRecentInquiries();
        if (items.length === 0) {
            recentInquiriesList.innerHTML = `
                <article class="thread-card thread-card-empty">
                    <span class="thread-ref">REF 00</span>
                    <h3>No inquiries yet.</h3>
                    <p>Ask the first grounded question and it will appear here as part of your current workspace trail.</p>
                </article>
            `;
            return;
        }

        recentInquiriesList.innerHTML = items.map((item, index) => `
            <article class="thread-card">
                <span class="thread-ref">REF ${String(index + 1).padStart(2, "0")}</span>
                <h3>${escapeHtml(item.question)}</h3>
                <p>${escapeHtml(item.mode)} retrieval stored in this browser session.</p>
            </article>
        `).join("");
    }

    function resetAnswerView() {
        answerBody.classList.add("hidden");
        citationsWrap.classList.add("hidden");
        answerMetrics.innerHTML = "";
        answerRefStrip.innerHTML = "";
        answerRefStrip.classList.add("hidden");
        answerText.innerHTML = "";
        answerDebug.textContent = "";
        answerDebug.classList.add("hidden");
        citationsList.innerHTML = "";
        if (previewPlaceholder) {
            previewPlaceholder.classList.remove("hidden");
        }
    }

    function setDeepResearchVisibility() {
        const selectedMode = modeInput.value || "hybrid";
        const enabled = deepResearchInput.checked;
        deepResearchPanel.classList.toggle("hidden", !enabled);
        let warningText = "";
        let warningTone = "warning";
        if (enabled) {
            warningText = "Deep Research scans more of the document, can increase system load, and may take significantly longer to answer. Use it only for important questions.";
        } else if (selectedMode === "graph_hybrid") {
            warningText = "Graph Hybrid is best for relational questions. It may take longer and does not automatically produce better answers for every query.";
        } else if (selectedMode === "full") {
            warningText = "Full mode uses the richest retrieval stack available. It can be slower and more expensive, and it does not guarantee a better answer for every question.";
        }
        deepResearchWarning.classList.toggle("hidden", !warningText);
        if (warningText) {
            setMessage(
                deepResearchWarning,
                warningTone,
                warningText
            );
        } else {
            deepResearchWarning.innerHTML = "";
        }
    }

    function syncModeGuide() {
        modeGuide.querySelectorAll(".mode-chip").forEach((chip) => {
            chip.classList.toggle("is-active", chip.dataset.modeOption === modeInput.value);
        });
    }

    function setAskProgress(progress, label) {
        askProgress.classList.remove("hidden");
        askProgressLabel.textContent = label;
        askProgressValue.textContent = `${Math.max(0, Math.min(100, Math.round(progress)))}%`;
        askProgressFill.style.width = `${Math.max(0, Math.min(100, progress))}%`;
    }

    function startAskProgress() {
        let stageIndex = 0;
        setAskProgress(ASK_STAGES[0].progress, ASK_STAGES[0].label);
        if (askProgressTimer) {
            window.clearInterval(askProgressTimer);
        }
        askProgressTimer = window.setInterval(() => {
            stageIndex = Math.min(stageIndex + 1, ASK_STAGES.length - 1);
            const stage = ASK_STAGES[stageIndex];
            setAskProgress(stage.progress, stage.label);
            if (stageIndex === ASK_STAGES.length - 1) {
                window.clearInterval(askProgressTimer);
                askProgressTimer = null;
            }
        }, 650);
    }

    function finishAskProgress(success, deepResearch) {
        if (askProgressTimer) {
            window.clearInterval(askProgressTimer);
            askProgressTimer = null;
        }
        if (success) {
            setAskProgress(100, deepResearch ? "Deep Research complete" : "Grounded answer ready");
        } else {
            setAskProgress(100, "Ask request failed");
        }
    }

    function currentFilters() {
        const sourceType = sourceTypeInput.value || null;
        return sourceType ? { source_type: sourceType } : null;
    }

    function activateCitation(citationId) {
        citationsList.querySelectorAll(".citation-card").forEach((element) => {
            element.classList.toggle("is-active", element.dataset.citationId === citationId);
        });
        answerRefStrip.querySelectorAll(".ref-pill").forEach((element) => {
            element.classList.toggle("is-active", element.dataset.citationTarget === citationId);
        });
    }

    async function submitAsk() {
        const question = questionInput.value.trim();
        if (!question) {
            setMessage(askMessage, "warning", "Enter a question before calling /ask.");
            return;
        }
        if (deepResearchInput.checked) {
            const confirmed = window.confirm(
                "Deep Research scans more of the document, can increase system load, and may take significantly longer to answer. Continue?"
            );
            if (!confirmed) {
                return;
            }
        }
        if (modeInput.value === "graph_hybrid" || modeInput.value === "full") {
            const confirmed = window.confirm(
                modeInput.value === "graph_hybrid"
                    ? "Graph Hybrid is best for relational questions and may take longer. It does not automatically give better results for every ask. Continue?"
                    : "Full mode uses the richest retrieval stack, may take longer, and does not automatically guarantee a better answer. Continue?"
            );
            if (!confirmed) {
                return;
            }
        }

        askSubmit.disabled = true;
        askMeta.textContent = "Submitting question...";
        setMessage(askMessage, "", "");
        answerState.textContent = "Waiting for grounded answer...";
        analysisCurrentInquiry.textContent = question;
        analysisModeBadge.textContent = formatModeLabel(modeInput.value || "hybrid");
        resetAnswerView();
        startAskProgress();

        try {
            const payload = {
                question,
                k_chunks: Number(kChunksInput.value || 6),
                filters: currentFilters(),
                mode: modeInput.value || null,
                dry_run: dryRunInput.checked,
                deep_research: deepResearchInput.checked,
                custom_query: customQueryInput.value.trim() || null,
                anchor_terms: splitTerms(anchorTermsInput.value),
                exact_phrase_bias: exactPhraseInput.value.trim() || null,
                expand_neighbors: expandNeighborsInput.checked,
                force_rare_keyword_scan: forceRareKeywordScanInput.checked,
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
            saveRecentInquiry(question, payload.mode || "hybrid");
            askMeta.textContent = `${payload.deep_research ? "Deep Research" : "Standard retrieval"} | mode=${payload.mode || "default"} | dry_run=${payload.dry_run}`;
            answerState.textContent = payload.dry_run ? "Prompt assembly complete." : "Grounded answer ready.";
            answerBody.classList.remove("hidden");
            analysisModeBadge.textContent = formatModeLabel(result.mode || payload.mode || "hybrid");
            answerMetrics.innerHTML = metricPills({ ...result, mode: result.mode || payload.mode || "hybrid" });
            answerText.innerHTML = answerParagraphs(result.answer || "No answer text returned.");
            finishAskProgress(true, payload.deep_research);

            const retrievalTrace = result?.debug_info?.retrieval_trace;
            if (retrievalTrace?.deep_research_used) {
                answerMetrics.innerHTML += `<span class="metric-pill">Deep Research</span>`;
            }
            if (retrievalTrace?.graph_used) {
                answerMetrics.innerHTML += `<span class="metric-pill">Graph Signals</span>`;
            }
            if (retrievalTrace?.temporal_used) {
                answerMetrics.innerHTML += `<span class="metric-pill">Temporal Signals</span>`;
            }

            if (result.debug_info) {
                answerDebug.classList.remove("hidden");
                answerDebug.textContent = JSON.stringify(result.debug_info, null, 2);
            }

            if (Array.isArray(result.citations) && result.citations.length > 0) {
                citationsWrap.classList.remove("hidden");
                citationsList.innerHTML = result.citations.map(citationCard).join("");
                answerRefStrip.classList.remove("hidden");
                answerRefStrip.innerHTML = refStrip(result.citations);
                if (previewPlaceholder) {
                    previewPlaceholder.classList.add("hidden");
                }
                activateCitation(String(result.citations[0].citation_id));
            } else if (!result.debug_info) {
                citationsWrap.classList.remove("hidden");
                citationsList.innerHTML = "<p class=\"muted-text\">No citations returned.</p>";
            }
        } catch (error) {
            finishAskProgress(false, deepResearchInput.checked);
            setHealth(false, "Ask request failed");
            setMessage(askMessage, "error", error.message);
            answerState.textContent = "Unable to complete the ask request.";
        } finally {
            askSubmit.disabled = false;
        }
    }

    answerRefStrip.addEventListener("click", (event) => {
        const button = event.target.closest(".ref-pill");
        if (!button) {
            return;
        }
        activateCitation(button.dataset.citationTarget || "");
    });

    citationsList.addEventListener("click", (event) => {
        const card = event.target.closest(".citation-card");
        if (!card) {
            return;
        }
        activateCitation(card.dataset.citationId || "");
    });

    askSubmit.addEventListener("click", submitAsk);
    deepResearchInput.addEventListener("change", setDeepResearchVisibility);
    modeInput.addEventListener("change", () => {
        syncModeGuide();
        setDeepResearchVisibility();
    });
    modeGuide.addEventListener("click", (event) => {
        const chip = event.target.closest(".mode-chip");
        if (!chip) {
            return;
        }
        modeInput.value = chip.dataset.modeOption || "hybrid";
        syncModeGuide();
    });
    setDeepResearchVisibility();
    syncModeGuide();
    renderRecentInquiries();
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function summarizeQuestion(value, limit = 72) {
    const compact = String(value || "").trim().replace(/\s+/g, " ");
    if (compact.length <= limit) {
        return compact;
    }
    return `${compact.slice(0, limit - 1)}...`;
}

function setMessage(container, tone, text) {
    if (!container) {
        return;
    }
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

function formatLocator(locator) {
    if (!locator) {
        return "n/a";
    }
    const raw = String(locator).trim();
    try {
        const parsed = JSON.parse(raw);
        if (parsed.page) {
            return `Page ${parsed.page}`;
        }
        if (parsed.page_start && parsed.page_end) {
            return `Pages ${parsed.page_start}-${parsed.page_end}`;
        }
        if (Array.isArray(parsed.pages) && parsed.pages.length > 0) {
            return `Pages ${parsed.pages.join(", ")}`;
        }
        if (parsed.slide) {
            return `Slide ${parsed.slide}`;
        }
        if (parsed.sheet) {
            return `Sheet ${parsed.sheet}`;
        }
        if (parsed.section) {
            return String(parsed.section);
        }
    } catch (_error) {
        // Keep raw locator text if it is not JSON.
    }
    return raw;
}

function refStrip(citations) {
    return citations.map((citation, index) => `
        <button type="button" class="ref-pill" data-citation-target="${escapeHtml(citation.citation_id)}">
            REF ${String(index + 1).padStart(2, "0")}
        </button>
    `).join("");
}

function citationCard(citation, index) {
    const locator = `<span>Locator: ${escapeHtml(formatLocator(citation.locator))}</span>`;
    return `
        <article class="citation-card" data-citation-id="${escapeHtml(citation.citation_id)}" data-citation-index="${index}">
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

function compareGroupCard(group) {
    return `
        <article class="compare-group-card">
            <div class="compare-group-head">
                <div>
                    <span class="source-chip">${escapeHtml(group.source_type)}</span>
                    <h3>${escapeHtml(group.file_name)}</h3>
                </div>
                <span class="muted-text">Source #${escapeHtml(group.source_id)}</span>
            </div>
            <div class="compare-group-metrics">
                <span class="metric-pill">${escapeHtml(group.citations?.length ?? 0)} citations</span>
            </div>
            <div class="compare-group-list">
                ${(group.citations || []).map((citation) => `
                    <article class="compare-citation-row">
                        <strong>${escapeHtml(citation.citation_id)}</strong>
                        <span>${escapeHtml(citation.locator || citation.heading || "Context")}</span>
                    </article>
                `).join("")}
            </div>
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
    const advancedToggle = document.getElementById("advanced-toggle");
    const advancedPanel = document.getElementById("advanced-panel");
    const askMeta = document.getElementById("ask-meta");
    const askMessage = document.getElementById("ask-message");
    const deepResearchWarning = document.getElementById("deep-research-warning");
    const answerState = document.getElementById("answer-state");
    const answerBody = document.getElementById("answer-body");
    const answerMetrics = document.getElementById("answer-metrics");
    const answerText = document.getElementById("answer-text");
    const answerDebug = document.getElementById("answer-debug");
    const answerRefStrip = document.getElementById("answer-ref-strip");
    const compareGroups = document.getElementById("compare-groups");
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
    const inquiryHighlightQuote = document.getElementById("inquiry-highlight-quote");
    const inquiryHighlightMeta = document.getElementById("inquiry-highlight-meta");
    const appTabs = Array.from(document.querySelectorAll(".nav-tab"));
    const tabPanels = Array.from(document.querySelectorAll("[data-tab-panel]"));
    const analysisSummaryGrid = document.getElementById("analysis-summary-grid");
    const summaryPath = document.getElementById("analysis-summary-path");
    const summaryModeDetail = document.getElementById("analysis-summary-mode-detail");
    const summaryScope = document.getElementById("analysis-summary-scope");
    const summaryCounts = document.getElementById("analysis-summary-counts");
    const summaryFallback = document.getElementById("analysis-summary-fallback");
    const summaryLatency = document.getElementById("analysis-summary-latency");
    const evidenceDetail = document.getElementById("evidence-detail");
    const evidenceDetailTitle = document.getElementById("evidence-detail-title");
    const evidenceDetailMeta = document.getElementById("evidence-detail-meta");
    const evidenceDetailSnippet = document.getElementById("evidence-detail-snippet");
    const evidenceContextList = document.getElementById("evidence-context-list");
    const evidencePrev = document.getElementById("evidence-prev");
    const evidenceNext = document.getElementById("evidence-next");
    const evidenceOpenSource = document.getElementById("evidence-open-source");
    const askSourceScope = document.getElementById("ask-source-scope");
    const askSourceScopeLabel = document.getElementById("ask-source-scope-label");
    const askSourceScopeClear = document.getElementById("ask-source-scope-clear");

    const RECENTS_KEY = "rag-master-thread-sessions";
    const ASK_STAGES = [
        { progress: 0, label: "Submitting question" },
        { progress: 12, label: "Receiving question" },
        { progress: 28, label: "Searching sources" },
        { progress: 46, label: "Merging evidence" },
        { progress: 68, label: "Preparing answer context" },
        { progress: 84, label: "Generating grounded answer" },
    ];
    const COMPARE_STAGES = [
        { progress: 0, label: "Submitting comparison" },
        { progress: 18, label: "Gathering selected sources" },
        { progress: 38, label: "Retrieving evidence per source" },
        { progress: 58, label: "Preparing grouped evidence" },
        { progress: 80, label: "Generating grounded comparison" },
    ];

    let askProgressTimer = null;
    let currentCitations = [];
    let activeCitationIndex = -1;
    let activeSourceScope = null;

    function autoSizeQuestionInput() {
        if (!questionInput) {
            return;
        }
        questionInput.style.height = "auto";
        const nextHeight = Math.min(questionInput.scrollHeight, 220);
        questionInput.style.height = `${Math.max(nextHeight, 56)}px`;
        questionInput.style.overflowY = questionInput.scrollHeight > 220 ? "auto" : "hidden";
    }

    function loadRecentSessions() {
        try {
            const raw = window.localStorage.getItem(RECENTS_KEY);
            const items = JSON.parse(raw || "[]");
            return Array.isArray(items) ? items : [];
        } catch (_error) {
            return [];
        }
    }

    function saveSession(session) {
        const key = `${session.type}:${session.question}:${session.saved_at}`;
        const next = [
            { ...session, storage_key: key },
            ...loadRecentSessions().filter((item) => item.question !== session.question || item.type !== session.type),
        ].slice(0, 8);

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
        const items = loadRecentSessions();
        if (items.length === 0) {
            recentInquiriesList.innerHTML = `
                <article class="thread-row thread-row-empty">
                    <h3>No inquiries yet.</h3>
                    <p>Ask the first grounded question to start a new thread.</p>
                </article>
            `;
            return;
        }

        recentInquiriesList.innerHTML = items.map((item) => `
            <button type="button" class="thread-row thread-row-button" data-thread-key="${escapeHtml(item.storage_key || "")}">
                <div>
                    <h3>${escapeHtml(summarizeQuestion(item.question))}</h3>
                    <p>${escapeHtml(item.saved_at ? new Date(item.saved_at).toLocaleString() : "Recent")} • ${escapeHtml(item.mode_label || item.mode || "Hybrid")} • ${escapeHtml(item.type === "compare" ? "Compare" : "Ask")}</p>
                </div>
                <span class="material-symbols-outlined">open_in_new</span>
            </button>
        `).join("");
    }

    function activateTab(name) {
        appTabs.forEach((tab) => {
            tab.classList.toggle("is-active", tab.dataset.tabTarget === name);
        });
        tabPanels.forEach((panel) => {
            panel.classList.toggle("is-active", panel.dataset.tabPanel === name);
        });
    }

    function syncAdvancedPanelLabel() {
        if (!advancedToggle) {
            return;
        }
        advancedToggle.textContent = advancedPanel.classList.contains("hidden") ? "Advanced Params" : "Hide Params";
    }

    function setAskProgress(progress, label) {
        askProgress.classList.remove("hidden");
        askProgressLabel.textContent = label;
        askProgressValue.textContent = `${Math.max(0, Math.min(100, Math.round(progress)))}%`;
        askProgressFill.style.width = `${Math.max(0, Math.min(100, progress))}%`;
    }

    function startProgress(stages) {
        let stageIndex = 0;
        setAskProgress(stages[0].progress, stages[0].label);
        if (askProgressTimer) {
            window.clearInterval(askProgressTimer);
        }
        askProgressTimer = window.setInterval(() => {
            stageIndex = Math.min(stageIndex + 1, stages.length - 1);
            const stage = stages[stageIndex];
            setAskProgress(stage.progress, stage.label);
            if (stageIndex === stages.length - 1) {
                window.clearInterval(askProgressTimer);
                askProgressTimer = null;
            }
        }, 700);
    }

    function finishProgress(success, label) {
        if (askProgressTimer) {
            window.clearInterval(askProgressTimer);
            askProgressTimer = null;
        }
        setAskProgress(100, success ? label : "Request failed");
    }

    async function readNdjsonStream(response, onEvent) {
        const reader = response.body?.getReader();
        if (!reader) {
            throw new Error("Streaming not supported by this browser.");
        }
        const decoder = new TextDecoder();
        let buffer = "";
        while (true) {
            const { value, done } = await reader.read();
            if (done) {
                break;
            }
            buffer += decoder.decode(value, { stream: true });
            let newlineIndex = buffer.indexOf("\n");
            while (newlineIndex >= 0) {
                const line = buffer.slice(0, newlineIndex).trim();
                buffer = buffer.slice(newlineIndex + 1);
                if (line) {
                    onEvent(JSON.parse(line));
                }
                newlineIndex = buffer.indexOf("\n");
            }
        }
        const tail = buffer.trim();
        if (tail) {
            onEvent(JSON.parse(tail));
        }
    }

    function resetAnswerView() {
        answerBody.classList.add("hidden");
        citationsWrap.classList.add("hidden");
        compareGroups.classList.add("hidden");
        analysisSummaryGrid.classList.add("hidden");
        answerMetrics.innerHTML = "";
        answerRefStrip.innerHTML = "";
        answerRefStrip.classList.add("hidden");
        answerText.innerHTML = "";
        answerDebug.textContent = "";
        answerDebug.classList.add("hidden");
        citationsList.innerHTML = "";
        compareGroups.innerHTML = "";
        currentCitations = [];
        activeCitationIndex = -1;
        evidenceContextList.innerHTML = "";
        evidenceContextList.classList.add("hidden");
        evidenceDetail.classList.add("hidden");
        if (previewPlaceholder) {
            previewPlaceholder.classList.remove("hidden");
        }
    }

    function setSourceScope(source) {
        activeSourceScope = source && source.id ? source : null;
        askSourceScope.classList.toggle("hidden", !activeSourceScope);
        if (!activeSourceScope) {
            askSourceScopeLabel.textContent = "Source scope not set";
            return;
        }
        askSourceScopeLabel.textContent = `${activeSourceScope.file_name} • Source #${activeSourceScope.id}`;
    }

    function setDeepResearchVisibility() {
        const selectedMode = modeInput.value || "hybrid";
        const enabled = deepResearchInput.checked;
        deepResearchPanel.classList.toggle("hidden", !enabled);
        let warningText = "";
        if (enabled) {
            warningText = "Deep Research scans more of the document, can increase system load, and may take significantly longer to answer. Use it only for important questions.";
        } else if (selectedMode === "graph_hybrid") {
            warningText = "Graph Hybrid is best for relational questions. It may take longer and does not automatically produce better answers for every query.";
        } else if (selectedMode === "full") {
            warningText = "Full mode uses the richest retrieval stack available. It can be slower and more expensive, and it does not guarantee a better answer for every question.";
        }
        deepResearchWarning.classList.toggle("hidden", !warningText);
        if (warningText) {
            setMessage(deepResearchWarning, "warning", warningText);
        } else {
            deepResearchWarning.innerHTML = "";
        }
    }

    function syncModeGuide() {
        modeGuide.querySelectorAll(".mode-chip").forEach((chip) => {
            chip.classList.toggle("is-active", chip.dataset.modeOption === modeInput.value);
        });
    }

    function currentFilters() {
        const filter = {};
        if (sourceTypeInput.value) {
            filter.source_type = sourceTypeInput.value;
        }
        if (activeSourceScope?.id) {
            filter.source_id = Number(activeSourceScope.id);
        }
        return Object.keys(filter).length > 0 ? filter : null;
    }

    function updateInquiryHighlight(result) {
        if (!inquiryHighlightQuote || !inquiryHighlightMeta) {
            return;
        }
        const citation = Array.isArray(result?.citations) && result.citations.length > 0 ? result.citations[0] : null;
        if (!citation) {
            inquiryHighlightQuote.textContent = "Upload sources and ask a grounded question to surface the most important cited evidence here.";
            inquiryHighlightMeta.innerHTML = `
                <span class="material-symbols-outlined">link</span>
                <span>No evidence highlighted yet.</span>
            `;
            return;
        }
        inquiryHighlightQuote.textContent = citation.snippet;
        inquiryHighlightMeta.innerHTML = `
            <span class="material-symbols-outlined">link</span>
            <span>${escapeHtml(citation.file_name)}${citation.locator ? ` • ${escapeHtml(formatLocator(citation.locator))}` : ""}</span>
        `;
    }

    function renderSummary({ modeLabel, question, result, sourceScope, compareMode = false }) {
        const trace = result?.debug_info?.retrieval_trace || {};
        analysisSummaryGrid.classList.remove("hidden");
        summaryPath.textContent = compareMode ? "Grouped compare" : (trace.retrieval_path_used || modeLabel);
        summaryModeDetail.textContent = [
            trace.graph_used ? "Graph signals" : null,
            trace.temporal_used ? "Temporal signals" : null,
            trace.deep_research_used ? "Deep Research" : null,
        ].filter(Boolean).join(" • ") || `Mode ${modeLabel}`;
        summaryScope.textContent = sourceScope
            ? `${sourceScope.file_name} • Source #${sourceScope.id}`
            : (compareMode ? "Selected sources" : "All searchable sources");
        const citationCount = Array.isArray(result?.citations) ? result.citations.length : 0;
        summaryCounts.textContent = `${citationCount} citation${citationCount === 1 ? "" : "s"} • ${result?.used_chunks_count ?? 0} used chunks`;
        summaryFallback.textContent = trace.fallback_reason || result?.debug_info?.fallback_reason || "No fallback reported";
        summaryLatency.textContent = `Question: ${summarizeQuestion(question, 56)} • ${result?.latency_ms ?? "n/a"} ms`;
    }

    function renderCompareGroups(sources) {
        if (!Array.isArray(sources) || sources.length === 0) {
            compareGroups.classList.add("hidden");
            compareGroups.innerHTML = "";
            return;
        }
        compareGroups.classList.remove("hidden");
        compareGroups.innerHTML = sources.map(compareGroupCard).join("");
    }

    async function loadCitationContext(citation) {
        if (!citation) {
            return;
        }
        evidenceDetail.classList.remove("hidden");
        previewPlaceholder.classList.add("hidden");
        evidenceDetailTitle.textContent = citation.file_name;
        evidenceDetailMeta.textContent = `${formatLocator(citation.locator) || citation.heading || "Context"} • Chunk ${citation.chunk_id} • Source #${citation.source_id}`;
        evidenceDetailSnippet.textContent = citation.snippet;
        evidenceContextList.innerHTML = "";
        evidenceContextList.classList.add("hidden");
        try {
            const response = await fetch(`${apiBase}/corpus/${citation.source_id}/chunks/${citation.chunk_id}/context?radius=1`);
            const payload = await response.json().catch(() => ({}));
            if (!response.ok) {
                throw new Error(payload?.detail?.message || payload?.detail?.error || "Unable to load source context.");
            }
            const neighbors = Array.isArray(payload?.neighbors) ? payload.neighbors : [];
            if (neighbors.length === 0) {
                return;
            }
            evidenceContextList.classList.remove("hidden");
            evidenceContextList.innerHTML = neighbors.map((item) => `
                <article class="context-card">
                    <div class="context-card-head">
                        <span class="source-chip">${escapeHtml(item.locator || `Chunk ${item.chunk_index}`)}</span>
                        <span class="muted-text">${escapeHtml(item.heading || "Neighbor context")}</span>
                    </div>
                    <p>${escapeHtml(item.chunk_text)}</p>
                </article>
            `).join("");
        } catch (_error) {
            evidenceContextList.classList.add("hidden");
        }
    }

    function activateCitation(target) {
        let citationId = target;
        if (typeof target === "number") {
            const citation = currentCitations[target];
            citationId = citation?.citation_id || "";
        }
        citationsList.querySelectorAll(".citation-card").forEach((element) => {
            element.classList.toggle("is-active", element.dataset.citationId === citationId);
        });
        answerRefStrip.querySelectorAll(".ref-pill").forEach((element) => {
            element.classList.toggle("is-active", element.dataset.citationTarget === citationId);
        });
        activeCitationIndex = currentCitations.findIndex((item) => String(item.citation_id) === String(citationId));
        if (activeCitationIndex >= 0) {
            loadCitationContext(currentCitations[activeCitationIndex]).catch(() => {});
        }
        evidencePrev.disabled = activeCitationIndex <= 0;
        evidenceNext.disabled = activeCitationIndex < 0 || activeCitationIndex >= currentCitations.length - 1;
    }

    function renderResult(result, sessionMeta) {
        answerBody.classList.remove("hidden");
        answerMetrics.innerHTML = metricPills({ ...result, mode: result.mode || sessionMeta.mode });
        if (sessionMeta.type === "compare") {
            answerText.innerHTML = answerParagraphs(result.answer || "No compare answer text returned.");
            renderCompareGroups(result.sources || []);
        } else {
            answerText.innerHTML = answerParagraphs(result.answer || "No answer text returned.");
            renderCompareGroups([]);
        }
        analysisModeBadge.textContent = formatModeLabel(result.mode || sessionMeta.mode || "hybrid");
        renderSummary({
            modeLabel: formatModeLabel(result.mode || sessionMeta.mode || "hybrid"),
            question: sessionMeta.question,
            result,
            sourceScope: sessionMeta.sourceScope || null,
            compareMode: sessionMeta.type === "compare",
        });

        answerDebug.textContent = "";
        answerDebug.classList.add("hidden");

        currentCitations = Array.isArray(result.citations) ? result.citations : [];
        if (currentCitations.length > 0) {
            citationsWrap.classList.remove("hidden");
            citationsList.innerHTML = currentCitations.map(citationCard).join("");
            answerRefStrip.classList.remove("hidden");
            answerRefStrip.innerHTML = refStrip(currentCitations);
            activateCitation(String(currentCitations[0].citation_id));
        } else {
            citationsWrap.classList.remove("hidden");
            citationsList.innerHTML = "<p class=\"muted-text\">No citations returned.</p>";
            previewPlaceholder.classList.remove("hidden");
            evidenceDetail.classList.add("hidden");
        }

        updateInquiryHighlight(result);
    }

    function buildSession({ type, question, mode, sourceScope, requestPayload, result }) {
        return {
            type,
            question,
            mode,
            mode_label: formatModeLabel(mode || result.mode || "hybrid"),
            saved_at: new Date().toISOString(),
            sourceScope,
            requestPayload,
            result,
        };
    }

    function restoreSession(session) {
        if (!session || !session.result) {
            return;
        }
        analysisCurrentInquiry.textContent = session.question || "Restored session";
        answerState.textContent = session.type === "compare" ? "Comparison restored." : "Grounded answer restored.";
        resetAnswerView();
        setSourceScope(session.type === "ask" ? (session.sourceScope || null) : null);
        renderResult(session.result, session);
        activateTab("analysis");
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
        activateTab("analysis");
        startProgress(ASK_STAGES);

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

        try {
            let response = await fetch(`${apiBase}/ask/stream`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });

            if (response.status === 404) {
                response = await fetch(`${apiBase}/ask`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
            }

            if (!response.ok) {
                const result = await response.json().catch(() => ({}));
                const detail = result?.detail;
                const message = typeof detail === "string"
                    ? detail
                    : detail?.message || detail?.error || `Ask failed: ${response.status}`;
                throw new Error(message);
            }

            let result = {};
            const isStreamResponse = String(response.headers.get("content-type") || "").includes("application/x-ndjson");
            if (isStreamResponse) {
                let finalResult = null;
                await readNdjsonStream(response, (event) => {
                    if (event?.type === "progress") {
                        setAskProgress(Number(event.progress || 0), String(event.label || "Working..."));
                        return;
                    }
                    if (event?.type === "result") {
                        finalResult = event.result || null;
                    }
                });
                result = finalResult || {};
            } else {
                result = await response.json().catch(() => ({}));
            }

            setHealth(true, "Backend connected");
            askMeta.textContent = `${payload.deep_research ? "Deep Research" : "Standard retrieval"} | mode=${payload.mode || "default"} | dry_run=${payload.dry_run}`;
            answerState.textContent = payload.dry_run ? "Prompt assembly complete." : "Grounded answer ready.";
            finishProgress(true, payload.deep_research ? "Deep Research complete" : "Grounded answer ready");

            const session = buildSession({
                type: "ask",
                question,
                mode: result.mode || payload.mode || "hybrid",
                sourceScope: activeSourceScope,
                requestPayload: payload,
                result,
            });
            saveSession(session);
            renderResult(result, session);
            activateTab("analysis");
        } catch (error) {
            finishProgress(false, "Ask failed");
            setHealth(false, "Ask request failed");
            setMessage(askMessage, "error", error.message);
            answerState.textContent = "Unable to complete the ask request.";
        } finally {
            askSubmit.disabled = false;
        }
    }

    async function submitCompare(detail) {
        const question = String(detail?.question || "").trim();
        const sourceIds = Array.isArray(detail?.sourceIds) ? detail.sourceIds.map(Number).filter(Boolean) : [];
        if (!question || sourceIds.length < 2) {
            setMessage(askMessage, "warning", "Select at least two sources and provide a compare question.");
            return;
        }
        if (detail?.mode === "graph_hybrid" || detail?.mode === "full") {
            const confirmed = window.confirm(
                detail.mode === "graph_hybrid"
                    ? "Graph Hybrid is best for relational comparisons and may take longer. Continue?"
                    : "Full mode uses the richest retrieval stack and may take longer without guaranteeing a better comparison. Continue?"
            );
            if (!confirmed) {
                return;
            }
        }

        askMeta.textContent = `Comparing ${sourceIds.length} sources...`;
        answerState.textContent = "Preparing grouped comparison...";
        analysisCurrentInquiry.textContent = question;
        analysisModeBadge.textContent = formatModeLabel(detail?.mode || "hybrid");
        resetAnswerView();
        activateTab("analysis");
        startProgress(COMPARE_STAGES);

        const payload = {
            question,
            source_ids: sourceIds,
            k_chunks_per_source: Number(detail?.kChunksPerSource || 4),
            mode: detail?.mode || "hybrid",
            dry_run: Boolean(detail?.dryRun),
        };

        try {
            const response = await fetch(`${apiBase}/compare`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload),
            });
            const result = await response.json().catch(() => ({}));
            if (!response.ok) {
                const detailValue = result?.detail;
                const message = typeof detailValue === "string"
                    ? detailValue
                    : detailValue?.message || detailValue?.error || `Compare failed: ${response.status}`;
                throw new Error(message);
            }

            setHealth(true, "Backend connected");
            answerState.textContent = payload.dry_run ? "Grouped compare prompt assembled." : "Grounded comparison ready.";
            finishProgress(true, "Comparison ready");
            const session = buildSession({
                type: "compare",
                question,
                mode: payload.mode,
                sourceScope: { id: sourceIds.join(","), file_name: `${sourceIds.length} selected sources` },
                requestPayload: payload,
                result,
            });
            saveSession(session);
            renderResult(result, session);
            activateTab("analysis");
        } catch (error) {
            finishProgress(false, "Compare failed");
            setHealth(false, "Compare request failed");
            setMessage(askMessage, "error", error.message);
            answerState.textContent = "Unable to complete the compare request.";
            activateTab("analysis");
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

    evidencePrev.addEventListener("click", () => {
        if (activeCitationIndex > 0) {
            activateCitation(activeCitationIndex - 1);
        }
    });

    evidenceNext.addEventListener("click", () => {
        if (activeCitationIndex >= 0 && activeCitationIndex < currentCitations.length - 1) {
            activateCitation(activeCitationIndex + 1);
        }
    });

    evidenceOpenSource.addEventListener("click", () => {
        const citation = currentCitations[activeCitationIndex];
        if (!citation) {
            return;
        }
        window.dispatchEvent(new CustomEvent("rag:open-source-request", {
            detail: {
                sourceId: citation.source_id,
            },
        }));
        activateTab("corpus");
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
        setDeepResearchVisibility();
    });
    appTabs.forEach((tab) => {
        tab.addEventListener("click", () => activateTab(tab.dataset.tabTarget || "inquiry"));
    });
    document.querySelectorAll("[data-tab-jump]").forEach((element) => {
        element.addEventListener("click", () => activateTab(element.getAttribute("data-tab-jump") || "inquiry"));
    });
    advancedToggle.addEventListener("click", () => {
        advancedPanel.classList.toggle("hidden");
        syncAdvancedPanelLabel();
    });
    questionInput.addEventListener("input", autoSizeQuestionInput);
    askSourceScopeClear.addEventListener("click", () => setSourceScope(null));
    recentInquiriesList.addEventListener("click", (event) => {
        const button = event.target.closest("[data-thread-key]");
        if (!button) {
            return;
        }
        const targetKey = button.getAttribute("data-thread-key");
        const session = loadRecentSessions().find((item) => item.storage_key === targetKey);
        if (session) {
            restoreSession(session);
        }
    });

    window.addEventListener("rag:source-scope-request", (event) => {
        const source = event.detail?.source || null;
        setSourceScope(source);
        activateTab("inquiry");
        questionInput.focus();
        askMeta.textContent = source ? `Scoped to source #${source.id}` : "Ready.";
    });

    window.addEventListener("rag:compare-request", (event) => {
        submitCompare(event.detail || {});
    });

    setDeepResearchVisibility();
    syncModeGuide();
    syncAdvancedPanelLabel();
    autoSizeQuestionInput();
    activateTab("inquiry");
    updateInquiryHighlight(null);
    renderRecentInquiries();
}

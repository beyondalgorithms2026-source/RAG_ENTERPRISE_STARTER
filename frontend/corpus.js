const DEFAULT_EMPTY = "<p class=\"corpus-empty\">No uploaded sources yet.</p>";
const JOB_STAGE_LABELS = {
    uploaded: { label: "Uploading file", progress: 12, tone: "pending" },
    parsing: { label: "Extracting text", progress: 35, tone: "pending" },
    source_parts: { label: "Organizing content", progress: 55, tone: "pending" },
    chunking: { label: "Preparing passages", progress: 72, tone: "pending" },
    embedding: { label: "Preparing search index", progress: 88, tone: "pending" },
    embedded: { label: "Ready", progress: 100, tone: "success" },
    deduplicated: { label: "Already uploaded", progress: 100, tone: "warning" },
    failed: { label: "Upload failed", progress: 100, tone: "error" },
};

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function statusClass(value) {
    const normalized = String(value || "").toLowerCase();
    if (normalized.includes("failed") || normalized.includes("error")) {
        return "error";
    }
    if (
        normalized.includes("queued") ||
        normalized.includes("processing") ||
        normalized.includes("chunk") ||
        normalized.includes("uploaded") ||
        normalized.includes("parsing") ||
        normalized.includes("embedding")
    ) {
        return "pending";
    }
    return "";
}

function normalizeValue(value) {
    return String(value || "").trim().toLowerCase();
}

function titleCase(value) {
    return String(value || "")
        .split(/[_\s-]+/)
        .filter(Boolean)
        .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
        .join(" ");
}

function describeJobState(item) {
    const status = normalizeValue(item?.status);
    const stage = normalizeValue(item?.stage);

    if (status === "failed" || stage === "failed") {
        return {
            statusText: "Upload failed",
            stageText: "Upload failed",
            progressLabel: "Upload failed",
            progress: 100,
            tone: "error",
        };
    }

    if (status === "skipped" || stage === "deduplicated") {
        return {
            statusText: "Already uploaded",
            stageText: "Already uploaded",
            progressLabel: "Already uploaded",
            progress: 100,
            tone: "warning",
        };
    }

    if (status === "completed" || stage === "embedded") {
        return {
            statusText: "Ready",
            stageText: "Ready",
            progressLabel: "Ready",
            progress: 100,
            tone: "success",
        };
    }

    const stageMeta = JOB_STAGE_LABELS[stage] || {
        label: "Processing upload",
        progress: status === "queued" ? 15 : 45,
        tone: "pending",
    };

    return {
        statusText: status === "queued" ? "Uploading file" : "In progress",
        stageText: stageMeta.label,
        progressLabel: stageMeta.label,
        progress: stageMeta.progress,
        tone: stageMeta.tone,
    };
}

function describeSourceStatus(field, value) {
    const normalized = normalizeValue(value);
    if (field === "ingestion") {
        if (normalized === "embedded") {
            return { label: "Ready", className: "" };
        }
        if (normalized === "failed") {
            return { label: "Upload failed", className: "error" };
        }
        if (normalized === "queued" || normalized === "processing" || normalized === "chunked") {
            return { label: "Processing", className: "pending" };
        }
    }
    if (field === "enrichment") {
        if (normalized === "completed") {
            return { label: "Enriched", className: "" };
        }
        if (normalized === "failed") {
            return { label: "Enrichment failed", className: "error" };
        }
        if (normalized === "processing") {
            return { label: "Enriching", className: "pending" };
        }
        if (normalized === "not_started") {
            return { label: "Not enriched", className: "" };
        }
    }
    return { label: titleCase(value || "unknown"), className: statusClass(value) };
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

export function initCorpus({ apiBase }) {
    const backendHealth = document.getElementById("backend-health");
    const corpusList = document.getElementById("corpus-list");
    const corpusMessage = document.getElementById("corpus-message");
    const corpusRefresh = document.getElementById("corpus-refresh");
    const compareSubmit = document.getElementById("compare-submit");
    const compareQuestion = document.getElementById("compare-question");
    const compareMode = document.getElementById("compare-mode");
    const compareDryRun = document.getElementById("compare-dry-run");
    const corpusFilterType = document.getElementById("corpus-filter-type");
    const corpusFilterStatus = document.getElementById("corpus-filter-status");
    const overviewHealthState = document.getElementById("overview-health-state");
    const overviewLastSync = document.getElementById("overview-last-sync");
    const overviewSourceCount = document.getElementById("overview-source-count");
    const overviewReadyCountCopy = document.getElementById("overview-ready-count-copy");
    const settingsHealthStatus = document.getElementById("settings-health-status");
    const settingsDefaultMode = document.getElementById("settings-default-mode");
    const settingsRerankStatus = document.getElementById("settings-rerank-status");
    const settingsGraphReadyCount = document.getElementById("settings-graph-ready-count");
    const settingsTemporalReadyCount = document.getElementById("settings-temporal-ready-count");
    const settingsEmbeddedCount = document.getElementById("settings-embedded-count");
    const settingsEnrichedCount = document.getElementById("settings-enriched-count");
    const settingsGraphStatus = document.getElementById("settings-graph-status");
    const settingsFullStatus = document.getElementById("settings-full-status");
    const settingsDeepResearchStatus = document.getElementById("settings-deep-research-status");
    const corpusTotalCount = document.getElementById("corpus-total-count");
    const corpusTotalCaption = document.getElementById("corpus-total-caption");
    const corpusReadyCount = document.getElementById("corpus-ready-count");
    const corpusPendingCount = document.getElementById("corpus-pending-count");
    const corpusEnrichedCount = document.getElementById("corpus-enriched-count");
    const corpusTotalCountSecondary = document.getElementById("corpus-total-count-secondary");
    const corpusReadyCountSecondary = document.getElementById("corpus-ready-count-secondary");
    const corpusPendingCountSecondary = document.getElementById("corpus-pending-count-secondary");
    const uploadJobCard = document.getElementById("upload-job-card");
    const jobId = document.getElementById("job-id");
    const jobStatus = document.getElementById("job-status");
    const jobStage = document.getElementById("job-stage");
    const jobSource = document.getElementById("job-source");
    const jobError = document.getElementById("job-error");
    const jobRefresh = document.getElementById("job-refresh");
    const jobProgressLabel = document.getElementById("job-progress-label");
    const jobProgressValue = document.getElementById("job-progress-value");
    const jobProgressFill = document.getElementById("job-progress-fill");
    const corpusDetail = document.getElementById("corpus-detail");
    const corpusDetailStatus = document.getElementById("corpus-detail-status");
    const corpusDetailPills = document.getElementById("corpus-detail-pills");
    const corpusDetailId = document.getElementById("corpus-detail-id");
    const corpusDetailType = document.getElementById("corpus-detail-type");
    const corpusDetailIngestion = document.getElementById("corpus-detail-ingestion");
    const corpusDetailEnrichment = document.getElementById("corpus-detail-enrichment");
    const corpusDetailInvestigate = document.getElementById("corpus-detail-investigate");
    const corpusDetailOpenFile = document.getElementById("corpus-detail-open-file");
    const corpusDetailClear = document.getElementById("corpus-detail-clear");

    let corpusItems = [];
    let selectedSourceIds = new Set();
    let activeDetailSourceId = null;

    async function fetchJson(path, options = {}) {
        const response = await fetch(`${apiBase}${path}`, options);
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
            const detail = payload?.detail;
            const message = typeof detail === "string"
                ? detail
                : detail?.message || detail?.error || `Request failed: ${response.status}`;
            throw new Error(message);
        }
        return payload;
    }

    function setHealth(isHealthy, text) {
        backendHealth.innerHTML = `
            <span class="status-dot"></span>
            <span>${escapeHtml(text)}</span>
        `;
        backendHealth.classList.toggle("is-error", !isHealthy);
        if (overviewHealthState) {
            overviewHealthState.textContent = isHealthy ? "Online" : "Unavailable";
        }
        if (overviewLastSync) {
            overviewLastSync.textContent = text;
        }
        if (settingsHealthStatus) {
            settingsHealthStatus.textContent = isHealthy ? "Online" : "Unavailable";
        }
    }

    function renderHealthSnapshot(payload) {
        const retrievalDefaults = payload?.retrieval_defaults || {};
        const features = payload?.features || {};
        const corpus = payload?.corpus || {};

        if (settingsDefaultMode) {
            settingsDefaultMode.textContent = String(retrievalDefaults.mode || "hybrid");
        }
        if (settingsRerankStatus) {
            settingsRerankStatus.textContent = retrievalDefaults.rerank_enabled ? "Enabled" : "Disabled";
        }
        if (settingsGraphReadyCount) {
            settingsGraphReadyCount.textContent = String(corpus.graph_ready_sources ?? 0);
        }
        if (settingsTemporalReadyCount) {
            settingsTemporalReadyCount.textContent = String(corpus.temporal_ready_sources ?? 0);
        }
        if (settingsEmbeddedCount) {
            settingsEmbeddedCount.textContent = String(corpus.embedded_sources ?? 0);
        }
        if (settingsEnrichedCount) {
            settingsEnrichedCount.textContent = String(corpus.enriched_sources ?? 0);
        }
        if (settingsGraphStatus) {
            settingsGraphStatus.textContent = features.graph_enabled
                ? ((corpus.graph_ready_sources || 0) > 0 ? "Enabled and ready" : "Enabled, waiting on source artifacts")
                : "Disabled";
        }
        if (settingsFullStatus) {
            settingsFullStatus.textContent = (features.graph_enabled || features.temporal_enabled)
                ? ((((corpus.graph_ready_sources || 0) > 0) || ((corpus.temporal_ready_sources || 0) > 0)) ? "Enabled and partially ready" : "Enabled, waiting on source artifacts")
                : "Disabled";
        }
        if (settingsDeepResearchStatus) {
            settingsDeepResearchStatus.textContent = features.deep_research_available ? "Available" : "Unavailable";
        }
    }

    function renderJobCard({ id, sourceId, statusText, stageText, progressLabel, progress, tone, errorText }) {
        uploadJobCard.classList.remove("hidden");
        uploadJobCard.dataset.jobTone = tone || "pending";
        jobId.textContent = id == null ? "-" : String(id);
        jobStatus.textContent = statusText || "-";
        jobStage.textContent = stageText || "-";
        jobSource.textContent = sourceId == null ? "-" : String(sourceId);
        jobProgressLabel.textContent = progressLabel || statusText || "-";
        jobProgressValue.textContent = `${Math.max(0, Math.min(100, Math.round(progress || 0)))}%`;
        jobProgressFill.style.width = `${Math.max(0, Math.min(100, progress || 0))}%`;
        jobError.textContent = errorText || "";
        jobError.classList.toggle("hidden", !errorText);
    }

    function showPendingJob({
        fileName,
        fileIndex = 0,
        fileCount = 1,
        statusText = "In progress",
        stageText = "",
        progress = null,
        tone = "pending",
        errorText = "",
    }) {
        const sequenceLabel = stageText || (fileCount > 1
            ? `Uploading ${fileIndex + 1} of ${fileCount}`
            : "Uploading file");
        const progressValue = progress == null
            ? (fileCount > 1 ? Math.min(80, 10 + Math.round((fileIndex / Math.max(fileCount, 1)) * 60)) : 12)
            : progress;
        renderJobCard({
            id: null,
            sourceId: null,
            statusText,
            stageText: sequenceLabel,
            progressLabel: fileName ? `Uploading ${fileName}` : "Uploading file",
            progress: progressValue,
            tone,
            errorText,
        });
    }

    function filteredItems() {
        return corpusItems.filter((item) => {
            const typeValue = corpusFilterType?.value || "";
            const statusValue = corpusFilterStatus?.value || "";
            if (typeValue && normalizeValue(item.source_type) !== normalizeValue(typeValue)) {
                return false;
            }
            if (!statusValue) {
                return true;
            }
            const ingestion = normalizeValue(item.ingestion_status);
            const enrichment = normalizeValue(item.enrichment_status);
            if (statusValue === "ready") {
                return ingestion === "embedded";
            }
            if (statusValue === "processing") {
                return ingestion !== "embedded" && ingestion !== "failed";
            }
            if (statusValue === "failed") {
                return ingestion === "failed" || enrichment === "failed";
            }
            if (statusValue === "enriched") {
                return enrichment === "completed";
            }
            return true;
        });
    }

    function updateCompareState() {
        if (compareSubmit) {
            compareSubmit.textContent = selectedSourceIds.size >= 2
                ? `Compare Selected (${selectedSourceIds.size})`
                : "Compare Selected";
        }
    }

    function renderDetail(item) {
        if (!item) {
            activeDetailSourceId = null;
            corpusDetail.classList.add("hidden");
            corpusDetailPills.innerHTML = "";
            corpusDetailOpenFile.classList.add("hidden");
            corpusDetailOpenFile.setAttribute("href", "#");
            return;
        }
        activeDetailSourceId = item.id;
        corpusDetail.classList.remove("hidden");
        corpusDetailStatus.textContent = `${describeSourceStatus("ingestion", item.ingestion_status).label} • ${describeSourceStatus("enrichment", item.enrichment_status).label}`;
        corpusDetailPills.innerHTML = `
            <span class="detail-pill">${escapeHtml(item.source_type)}</span>
            <span class="detail-pill">${escapeHtml(describeSourceStatus("ingestion", item.ingestion_status).label)}</span>
            <span class="detail-pill">${escapeHtml(describeSourceStatus("enrichment", item.enrichment_status).label)}</span>
        `;
        corpusDetailId.textContent = String(item.id);
        corpusDetailType.textContent = item.source_type;
        corpusDetailIngestion.textContent = item.ingestion_status;
        corpusDetailEnrichment.textContent = item.enrichment_status;
        corpusDetailOpenFile.classList.remove("hidden");
        corpusDetailOpenFile.setAttribute("href", `${apiBase}/corpus/${item.id}/file`);
    }

    function renderCorpus(items) {
        const visibleItems = items;
        if (!Array.isArray(visibleItems) || visibleItems.length === 0) {
            corpusList.innerHTML = DEFAULT_EMPTY;
            updateSummaryCounts(corpusItems);
            renderDetail(null);
            updateCompareState();
            return;
        }

        updateSummaryCounts(corpusItems);
        corpusList.innerHTML = visibleItems.map((item) => `
            <article class="corpus-item ${activeDetailSourceId === item.id ? "is-active" : ""}" data-source-id="${escapeHtml(item.id)}">
                <div class="corpus-item-select">
                    <label class="selection-check">
                        <input type="checkbox" class="corpus-select" data-source-id="${escapeHtml(item.id)}" ${selectedSourceIds.has(item.id) ? "checked" : ""}>
                        <span>Select</span>
                    </label>
                </div>
                <div class="corpus-item-body">
                    <div class="corpus-item-head">
                        <div>
                            <h3 class="corpus-title">${escapeHtml(item.file_name)}</h3>
                            <div class="corpus-primary">
                                <span class="source-chip">${escapeHtml(item.source_type)}</span>
                                <span class="status-chip ${escapeHtml(describeSourceStatus("ingestion", item.ingestion_status).className)}">${escapeHtml(describeSourceStatus("ingestion", item.ingestion_status).label)}</span>
                                <span class="status-chip ${escapeHtml(describeSourceStatus("enrichment", item.enrichment_status).className)}">${escapeHtml(describeSourceStatus("enrichment", item.enrichment_status).label)}</span>
                            </div>
                        </div>
                        <div class="corpus-side">
                            <span class="corpus-id">Source #${escapeHtml(item.id)}</span>
                            <div class="row-actions">
                                <button type="button" class="button-secondary corpus-open" data-source-id="${escapeHtml(item.id)}">Inspect</button>
                                <button type="button" class="button-secondary corpus-investigate" data-source-id="${escapeHtml(item.id)}">Investigate</button>
                                <button type="button" class="button-secondary corpus-delete" data-source-id="${escapeHtml(item.id)}">Delete</button>
                            </div>
                        </div>
                    </div>
                    <p class="corpus-note">Ready for source-scoped investigation, comparison, and grounded evidence review.</p>
                </div>
            </article>
        `).join("");

        corpusList.querySelectorAll(".corpus-select").forEach((input) => {
            input.addEventListener("change", () => {
                const sourceId = Number(input.getAttribute("data-source-id"));
                if (!sourceId) {
                    return;
                }
                if (input.checked) {
                    selectedSourceIds.add(sourceId);
                } else {
                    selectedSourceIds.delete(sourceId);
                }
                updateCompareState();
            });
        });

        corpusList.querySelectorAll(".corpus-open").forEach((button) => {
            button.addEventListener("click", () => {
                const sourceId = Number(button.getAttribute("data-source-id"));
                const item = corpusItems.find((row) => row.id === sourceId);
                renderDetail(item || null);
                renderCorpus(filteredItems());
            });
        });

        corpusList.querySelectorAll(".corpus-investigate").forEach((button) => {
            button.addEventListener("click", () => {
                const sourceId = Number(button.getAttribute("data-source-id"));
                const item = corpusItems.find((row) => row.id === sourceId);
                if (!item) {
                    return;
                }
                renderDetail(item);
                window.dispatchEvent(new CustomEvent("rag:source-scope-request", {
                    detail: {
                        source: {
                            id: item.id,
                            file_name: item.file_name,
                            source_type: item.source_type,
                        },
                    },
                }));
            });
        });

        corpusList.querySelectorAll(".corpus-delete").forEach((button) => {
            button.addEventListener("click", async () => {
                const sourceId = button.getAttribute("data-source-id");
                if (!sourceId) {
                    return;
                }
                button.disabled = true;
                setMessage(corpusMessage, "", "");
                try {
                    await fetchJson(`/corpus/${sourceId}`, { method: "DELETE" });
                    selectedSourceIds.delete(Number(sourceId));
                    if (activeDetailSourceId === Number(sourceId)) {
                        renderDetail(null);
                    }
                    await refreshCorpus();
                    setMessage(corpusMessage, "success", `Deleted source #${sourceId}.`);
                } catch (error) {
                    setMessage(corpusMessage, "error", error.message);
                    button.disabled = false;
                }
            });
        });
    }

    function updateSummaryCounts(items) {
        const total = items.length;
        const ready = items.filter((item) => normalizeValue(item.ingestion_status) === "embedded").length;
        const pending = items.filter((item) => {
            const status = normalizeValue(item.ingestion_status);
            return status && status !== "embedded" && status !== "failed";
        }).length;
        const enriched = items.filter((item) => normalizeValue(item.enrichment_status) === "completed").length;

        if (overviewSourceCount) {
            overviewSourceCount.textContent = String(total);
        }
        if (overviewReadyCountCopy) {
            overviewReadyCountCopy.textContent = `${ready} ready`;
        }
        if (corpusTotalCount) {
            corpusTotalCount.textContent = String(total);
        }
        if (corpusTotalCaption) {
            corpusTotalCaption.textContent = `${total} document${total === 1 ? "" : "s"}`;
        }
        if (corpusReadyCount) {
            corpusReadyCount.textContent = String(ready);
        }
        if (corpusPendingCount) {
            corpusPendingCount.textContent = String(pending);
        }
        if (corpusEnrichedCount) {
            corpusEnrichedCount.textContent = String(enriched);
        }
        if (corpusTotalCountSecondary) {
            corpusTotalCountSecondary.textContent = `${enriched} enriched`;
        }
        if (corpusReadyCountSecondary) {
            corpusReadyCountSecondary.textContent = `${ready} searchable`;
        }
        if (corpusPendingCountSecondary) {
            corpusPendingCountSecondary.textContent = `${pending} in flight`;
        }
        if (overviewLastSync) {
            overviewLastSync.textContent = `Last refreshed ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
        }
    }

    async function refreshCorpus() {
        setMessage(corpusMessage, "", "");
        try {
            const items = await fetchJson("/corpus");
            corpusItems = Array.isArray(items) ? items : [];
            if (activeDetailSourceId != null) {
                const active = corpusItems.find((item) => item.id === activeDetailSourceId) || null;
                renderDetail(active);
            }
            renderCorpus(filteredItems());
            setMessage(corpusMessage, "success", `Loaded ${items.length} source(s).`);
            return items;
        } catch (error) {
            corpusList.innerHTML = DEFAULT_EMPTY;
            setMessage(corpusMessage, "error", error.message);
            throw error;
        }
    }

    async function refreshJob(jobIdValue) {
        if (!jobIdValue) {
            return null;
        }

        try {
            const item = await fetchJson(`/corpus/jobs/${jobIdValue}`);
            const display = describeJobState(item);
            renderJobCard({
                id: item.id,
                sourceId: item.source_id,
                statusText: display.statusText,
                stageText: display.stageText,
                progressLabel: display.progressLabel,
                progress: display.progress,
                tone: display.tone,
                errorText: item.error_message || "",
            });
            return item;
        } catch (error) {
            renderJobCard({
                id: jobIdValue,
                sourceId: null,
                statusText: "Unavailable",
                stageText: "Job status unavailable",
                progressLabel: "Unable to load job status",
                progress: 100,
                tone: "error",
                errorText: error.message,
            });
            throw error;
        }
    }

    async function bootstrap() {
        try {
            const health = await fetchJson("/health");
            setHealth(true, `Backend ${health.status}`);
            renderHealthSnapshot(health);
        } catch (_error) {
            setHealth(false, "Backend unreachable");
        }

        try {
            await refreshCorpus();
        } catch (_error) {
            // Message already rendered.
        }
    }

    corpusRefresh.addEventListener("click", () => {
        refreshCorpus().catch(() => {});
    });

    jobRefresh.addEventListener("click", () => {
        const currentJobId = jobId.textContent !== "-" ? jobId.textContent : "";
        refreshJob(currentJobId).catch(() => {});
    });

    [corpusFilterType, corpusFilterStatus].forEach((element) => {
        element?.addEventListener("change", () => {
            renderCorpus(filteredItems());
        });
    });

    compareSubmit?.addEventListener("click", () => {
        const sourceIds = Array.from(selectedSourceIds.values());
        if (sourceIds.length < 2) {
            setMessage(corpusMessage, "warning", "Select at least two sources before comparing.");
            return;
        }
        const question = String(compareQuestion?.value || "").trim();
        if (!question) {
            setMessage(corpusMessage, "warning", "Write a compare question first.");
            return;
        }
        window.dispatchEvent(new CustomEvent("rag:compare-request", {
            detail: {
                question,
                sourceIds,
                mode: compareMode?.value || "hybrid",
                dryRun: Boolean(compareDryRun?.checked),
                kChunksPerSource: 4,
            },
        }));
    });

    corpusDetailInvestigate?.addEventListener("click", () => {
        if (activeDetailSourceId == null) {
            return;
        }
        const item = corpusItems.find((row) => row.id === activeDetailSourceId);
        if (!item) {
            return;
        }
        window.dispatchEvent(new CustomEvent("rag:source-scope-request", {
            detail: {
                source: {
                    id: item.id,
                    file_name: item.file_name,
                    source_type: item.source_type,
                },
            },
        }));
    });

    corpusDetailClear?.addEventListener("click", () => {
        renderDetail(null);
        renderCorpus(filteredItems());
    });

    window.addEventListener("rag:open-source-request", (event) => {
        const sourceId = Number(event.detail?.sourceId);
        if (!sourceId) {
            return;
        }
        const item = corpusItems.find((row) => row.id === sourceId) || null;
        renderDetail(item);
        renderCorpus(filteredItems());
    });

    updateCompareState();

    return {
        bootstrap,
        refreshCorpus,
        refreshJob,
        showPendingJob,
        setHealth,
    };
}

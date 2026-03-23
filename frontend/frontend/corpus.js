const DEFAULT_EMPTY = "<p class=\"muted-text\">No uploaded sources yet.</p>";
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
            isTerminal: true,
        };
    }

    if (status === "skipped" || stage === "deduplicated") {
        return {
            statusText: "Already uploaded",
            stageText: "Already uploaded",
            progressLabel: "Already uploaded",
            progress: 100,
            tone: "warning",
            isTerminal: true,
        };
    }

    if (status === "completed" || stage === "embedded") {
        return {
            statusText: "Ready",
            stageText: "Ready",
            progressLabel: "Ready",
            progress: 100,
            tone: "success",
            isTerminal: true,
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
        isTerminal: false,
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

    function renderCorpus(items) {
        if (!Array.isArray(items) || items.length === 0) {
            corpusList.innerHTML = DEFAULT_EMPTY;
            return;
        }

        corpusList.innerHTML = items.map((item) => `
            <article class="corpus-item">
                <div class="corpus-item-head">
                    <div>
                        <h3>${escapeHtml(item.file_name)}</h3>
                        <div class="corpus-meta">
                            <span class="source-chip">${escapeHtml(item.source_type)}</span>
                            <span class="status-chip ${escapeHtml(describeSourceStatus("ingestion", item.ingestion_status).className)}">${escapeHtml(describeSourceStatus("ingestion", item.ingestion_status).label)}</span>
                            <span class="status-chip ${escapeHtml(describeSourceStatus("enrichment", item.enrichment_status).className)}">${escapeHtml(describeSourceStatus("enrichment", item.enrichment_status).label)}</span>
                        </div>
                    </div>
                    <div class="field-row">
                        <span class="muted-text">Source #${escapeHtml(item.id)}</span>
                        <button type="button" class="button-secondary corpus-delete" data-source-id="${escapeHtml(item.id)}">
                            Delete
                        </button>
                    </div>
                </div>
                <div class="corpus-meta">
                    <span>Path: ${escapeHtml(item.storage_path)}</span>
                    <span>Bytes: ${escapeHtml(item.file_size_bytes ?? "n/a")}</span>
                    <span>Hash: ${escapeHtml(item.hash_sha256)}</span>
                </div>
            </article>
        `).join("");

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
                    await refreshCorpus();
                    setMessage(corpusMessage, "success", `Deleted source #${sourceId}.`);
                } catch (error) {
                    setMessage(corpusMessage, "error", error.message);
                    button.disabled = false;
                }
            });
        });
    }

    async function refreshCorpus() {
        setMessage(corpusMessage, "", "");
        try {
            const items = await fetchJson("/corpus");
            renderCorpus(items);
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
        } catch (error) {
            setHealth(false, "Backend unreachable");
        }

        try {
            await refreshCorpus();
        } catch (error) {
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

    return {
        bootstrap,
        refreshCorpus,
        refreshJob,
        showPendingJob,
        setHealth,
    };
}

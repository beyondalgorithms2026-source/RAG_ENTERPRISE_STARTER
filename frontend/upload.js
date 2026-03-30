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

export function initUpload({ apiBase, refreshCorpus, refreshJob, showPendingJob, setHealth }) {
    const fileInput = document.getElementById("upload-file");
    const uploadSubmit = document.getElementById("upload-submit");
    const uploadMessage = document.getElementById("upload-message");
    const uploadFileName = document.getElementById("upload-file-name");
    const dropzone = document.getElementById("upload-dropzone");

    function currentFiles() {
        return fileInput.files ? Array.from(fileInput.files) : [];
    }

    function updateFileLabel() {
        const files = currentFiles();
        if (files.length === 0) {
            uploadFileName.textContent = "No files selected";
            return;
        }
        if (files.length === 1) {
            uploadFileName.textContent = `${files[0].name} (${files[0].size} bytes)`;
            return;
        }
        const totalBytes = files.reduce((sum, file) => sum + (file.size || 0), 0);
        uploadFileName.textContent = `${files.length} files selected (${totalBytes} bytes total)`;
    }

    async function waitForCompletedJob(jobId) {
        let latest = null;
        for (let attempt = 0; attempt < 8; attempt += 1) {
            latest = await refreshJob(jobId).catch(() => null);
            if (!latest) {
                break;
            }
            if (latest.status === "completed" || latest.status === "failed" || latest.status === "skipped") {
                return latest;
            }
            await new Promise((resolve) => window.setTimeout(resolve, 250));
        }
        return latest;
    }

    async function uploadSingleFile(file) {
        const payload = new FormData();
        payload.append("file", file);
        const response = await fetch(`${apiBase}/upload`, {
            method: "POST",
            body: payload,
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) {
            const detail = result?.detail;
            const message = typeof detail === "string"
                ? detail
                : detail?.message || detail?.error || `Upload failed: ${response.status}`;
            throw new Error(message);
        }
        return result;
    }

    async function submitUpload() {
        const files = currentFiles();
        if (files.length === 0) {
            setMessage(uploadMessage, "warning", "Choose one or more supported files before uploading.");
            return;
        }

        uploadSubmit.disabled = true;
        setMessage(uploadMessage, "", "");

        try {
            const items = [];
            for (const [index, file] of files.entries()) {
                if (typeof showPendingJob === "function") {
                    showPendingJob({ fileName: file.name, fileIndex: index, fileCount: files.length });
                }
                setMessage(
                    uploadMessage,
                    "warning",
                    files.length > 1
                        ? `Uploading ${index + 1} of ${files.length}: ${file.name}`
                        : `Uploading ${file.name}`
                );
                const item = await uploadSingleFile(file);
                items.push(item);
                const latestJob = await waitForCompletedJob(item.job_id);
                if (latestJob?.status === "failed") {
                    throw new Error(latestJob.error_message || `Upload processing failed for ${file.name}.`);
                }
                await refreshCorpus().catch(() => {});
            }

            const latestItem = items[items.length - 1];
            const uploadedNames = items
                .filter((item) => item.status !== "skipped")
                .map((item) => item.file_name);
            const skippedNames = items
                .filter((item) => item.status === "skipped")
                .map((item) => item.file_name);

            setHealth(true, "Backend connected");
            updateFileLabel();
            if (uploadedNames.length > 0 && skippedNames.length > 0) {
                setMessage(
                    uploadMessage,
                    "success",
                    `Ready: ${uploadedNames.join(", ")}. Already uploaded: ${skippedNames.join(", ")}.`
                );
            } else if (uploadedNames.length > 0) {
                setMessage(
                    uploadMessage,
                    "success",
                    `${uploadedNames.length} file(s) ready. Latest processed source: ${latestItem.file_name}.`
                );
            } else if (skippedNames.length > 0) {
                setMessage(
                    uploadMessage,
                    "warning",
                    `Already uploaded: ${skippedNames.join(", ")}.`
                );
            }
        } catch (error) {
            if (typeof showPendingJob === "function") {
                showPendingJob({
                    fileName: files[0]?.name || "",
                    fileCount: files.length,
                    statusText: "Upload failed",
                    stageText: "Upload request failed",
                    progress: 100,
                    tone: "error",
                    errorText: error.message,
                });
            }
            setMessage(uploadMessage, "error", error.message);
            setHealth(false, "Upload failed");
        } finally {
            uploadSubmit.disabled = false;
        }
    }

    ["dragenter", "dragover"].forEach((eventName) => {
        dropzone.addEventListener(eventName, (event) => {
            event.preventDefault();
            dropzone.classList.add("drag-active");
        });
    });

    ["dragleave", "drop"].forEach((eventName) => {
        dropzone.addEventListener(eventName, (event) => {
            event.preventDefault();
            dropzone.classList.remove("drag-active");
        });
    });

    dropzone.addEventListener("drop", (event) => {
        const files = event.dataTransfer?.files;
        if (files && files.length > 0) {
            fileInput.files = files;
            updateFileLabel();
        }
    });

    fileInput.addEventListener("change", updateFileLabel);
    uploadSubmit.addEventListener("click", submitUpload);
}

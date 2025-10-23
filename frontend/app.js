(() => {
  const { createApp, ref, onMounted } = Vue;

  // Configure PDF.js worker if available; fail gracefully if not.
  if (window.pdfjsLib && window.pdfjsLib.GlobalWorkerOptions) {
    window.pdfjsLib.GlobalWorkerOptions.workerSrc =
      "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js";
  } else {
    console.warn("PDF.js not loaded; PDF preview/highlight disabled.");
  }

  function bytesToMB(bytes) {
    return bytes / (1024 * 1024);
  }

  const App = {
    setup() {
      const file = ref(null);
      const pdfBuffer = ref(null);
      const message = ref("");
      const issues = ref([]);
      const summary = ref("");
      const limits = ref({ maxFileMb: (window.APP_CONFIG?.MAX_FILE_MB ?? 5) });
      const loading = ref(false);
      const apiBase = ref(window.APP_CONFIG?.API_BASE_URL || "");
      const isDocx = ref(false);

      function onFileChange(e) {
        const f = e.target.files?.[0];
        file.value = f || null;
        issues.value = [];
        message.value = "";
        summary.value = "";
        isDocx.value = false;
        if (f && f.type === "application/pdf") {
          const r = new FileReader();
          r.onload = () => {
            pdfBuffer.value = r.result;
            renderPDF(r.result);
          };
          r.readAsArrayBuffer(f);
        } else {
          pdfBuffer.value = null;
          document.getElementById("pdf-container").innerHTML = "";
          if (f && f.name?.toLowerCase().endsWith('.docx')) {
            isDocx.value = true;
          }
        }
      }

      async function analyze() {
        try {
          if (!apiBase.value) {
            message.value = "Configure API_BASE_URL in frontend/config.js";
            return;
          }
          if (!file.value) {
            message.value = "Pick a PDF or DOCX";
            return;
          }
          if (bytesToMB(file.value.size) > limits.value.maxFileMb) {
            message.value = `File too large (> ${limits.value.maxFileMb} MB)`;
            return;
          }
          loading.value = true;
          message.value = "Requesting upload URL...";

          const ext = file.value.name.toLowerCase().endsWith(".docx") ? "docx" : "pdf";
          const pres = await fetch(`${apiBase.value}/upload-url`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ext })
          }).then(r => r.ok ? r.json() : r.text().then(t => Promise.reject(t)));

          message.value = "Uploading to S3...";
          await fetch(pres.url, {
            method: "PUT",
            headers: { "Content-Type": pres.content_type },
            body: file.value
          }).then(r => {
            if (!r.ok) return r.text().then(t => Promise.reject(t));
          });

          message.value = "Analyzing with Bedrock (Nova Lite)...";
          const res = await fetch(`${apiBase.value}/analyze`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ s3_key: pres.key })
          }).then(r => r.ok ? r.json() : r.text().then(t => Promise.reject(t)));

          issues.value = res.issues || [];
          summary.value = res.summary || "";
          message.value = `Found ${issues.value.length} issues`;

          // Highlight snippets if we have a PDF preview
          if (pdfBuffer.value && issues.value.length) {
            highlightIssues(issues.value);
          }
        } catch (e) {
          console.error(e);
          message.value = `Error: ${e}`;
        } finally {
          loading.value = false;
        }
      }

      async function renderPDF(arrayBuffer) {
        if (!window.pdfjsLib) {
          console.warn("PDF.js missing; cannot render PDF preview.");
          return;
        }
        const container = document.getElementById("pdf-container");
        container.innerHTML = "";
        const pdf = await window.pdfjsLib.getDocument({ data: arrayBuffer }).promise;
        for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
          const page = await pdf.getPage(pageNum);
          const viewport = page.getViewport({ scale: 1.3 });
          const pageDiv = document.createElement("div");
          pageDiv.className = "page";
          pageDiv.style.width = `${viewport.width}px`;
          pageDiv.style.height = `${viewport.height}px`;
          pageDiv.id = `page-${pageNum}`;

          const canvas = document.createElement("canvas");
          const ctx = canvas.getContext("2d");
          canvas.width = viewport.width;
          canvas.height = viewport.height;
          pageDiv.appendChild(canvas);

          const textLayerDiv = document.createElement("div");
          textLayerDiv.className = "textLayer";
          pageDiv.appendChild(textLayerDiv);

          container.appendChild(pageDiv);

          await page.render({ canvasContext: ctx, viewport }).promise;
          try {
            const textContent = await page.getTextContent();
            if (window.pdfjsLib.renderTextLayer) {
              await window.pdfjsLib.renderTextLayer({
                textContent,
                container: textLayerDiv,
                viewport,
                textDivs: [],
                enhanceTextSelection: true,
              }).promise;
            } else {
              // Minimal fallback: dump text spans (no positioning enhancements)
              textContent.items.forEach((item) => {
                const span = document.createElement("span");
                span.textContent = item.str + " ";
                textLayerDiv.appendChild(span);
              });
            }
          } catch (e) {
            console.warn("Text layer render failed", e);
          }
        }
      }

      function normalizeWs(s) { return (s || "").replace(/\s+/g, " ").trim(); }

      function highlightIssues(list) {
        // Simple pass: try to find each exact_text_snippet within any single text span per page.
        list.forEach(issue => {
          (issue.page_numbers || []).forEach(p => {
            const layer = document.querySelector(`#page-${p} .textLayer`);
            if (!layer || !issue.exact_text_snippet) return;
            const needleNorm = normalizeWs(issue.exact_text_snippet);
            const spans = Array.from(layer.querySelectorAll("span"));
            for (const span of spans) {
              const textNorm = normalizeWs(span.textContent);
              if (!textNorm) continue;
              if (textNorm.includes(needleNorm)) {
                // Wrap the match
                const idx = textNorm.indexOf(needleNorm);
                const raw = span.textContent;
                // Approximate mapping using original raw string (may differ slightly with whitespace)
                const before = raw.slice(0, idx);
                const match = raw.slice(idx, idx + issue.exact_text_snippet.length);
                const after = raw.slice(idx + issue.exact_text_snippet.length);
                span.innerHTML = "";
                const b = document.createTextNode(before);
                const m = document.createElement("span");
                m.className = "highlight";
                m.textContent = match || issue.exact_text_snippet;
                const a = document.createTextNode(after);
                span.appendChild(b);
                span.appendChild(m);
                span.appendChild(a);
                break; // one highlight per issue per page (keep it simple)
              }
            }
          });
        });
      }

      function scrollToPage(issue) {
        const p = issue.page_numbers?.[0];
        if (!p) return;
        document.getElementById(`page-${p}`)?.scrollIntoView({ behavior: "smooth" });
      }

      onMounted(() => {
        if (!apiBase.value) {
          message.value = "Set API_BASE_URL in frontend/config.js";
        }
      });

      function openGithub() {
        window.open('https://github.com/', '_blank');
      }

      return { file, pdfBuffer, message, issues, summary, limits, loading, isDocx, onFileChange, analyze, scrollToPage, openGithub };
    }
  };

  createApp(App).mount('#app');
})();

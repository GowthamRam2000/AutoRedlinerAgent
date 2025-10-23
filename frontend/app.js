(() => {
  const { createApp, ref, onMounted } = Vue;

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
      let pdfDocVar = null;
      const message = ref("");
      const issues = ref([]);
      const summary = ref("");
      const limits = ref({ maxFileMb: (window.APP_CONFIG?.MAX_FILE_MB ?? 5) });
      const loading = ref(false);
      const apiBase = ref(window.APP_CONFIG?.API_BASE_URL || "");
      const isDocx = ref(false);
      // Zoom / scale state
      const scaleMode = ref('fit'); // 'fit' or 'fixed'
      const scale = ref(1.0);       // used when scaleMode === 'fixed'
      const scaleUsed = ref(1.0);   // last effective scale used during render

      function onFileChange(e) {
        const f = e.target.files?.[0];
        file.value = f || null;
        issues.value = [];
        message.value = "";
        summary.value = "";
        isDocx.value = false;
        if (f && (f.type === "application/pdf" || f.name?.toLowerCase().endsWith('.pdf'))) {
          const r = new FileReader();
          r.onload = async () => {
            try {
              const data = new Uint8Array(r.result);
              pdfBuffer.value = data;
              pdfDocVar = await window.pdfjsLib.getDocument({ data }).promise;
              await renderPDF();
            } catch (err) {
              console.error(err);
              message.value = `Failed to load PDF: ${err}`;
            }
          };
          r.readAsArrayBuffer(f);
        } else {
          pdfBuffer.value = null;
          pdfDocVar = null;
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

      let renderSeq = 0;
      async function renderPDF() {
        if (!window.pdfjsLib || !pdfDocVar) {
          console.warn("PDF.js missing; cannot render PDF preview.");
          return;
        }
        const container = document.getElementById("pdf-container");
        const viewportEl = document.getElementById("viewer-viewport") || container.parentElement || document.body;
        container.innerHTML = "";
        const mySeq = ++renderSeq;
        const pdf = pdfDocVar;
        for (let pageNum = 1; pageNum <= pdf.numPages; pageNum++) {
          if (mySeq !== renderSeq) return;
          const page = await pdf.getPage(pageNum);
          const baseVp = page.getViewport({ scale: 1 });
          let s = scale.value;
          if (scaleMode.value === 'fit') {
            const vw = viewportEl.clientWidth || window.innerWidth;
            const maxWidth = Math.max(360, Math.min(1200, vw - 48));
            s = Math.max(0.6, Math.min(2.5, maxWidth / baseVp.width));
          }
          const viewport = page.getViewport({ scale: s });
          if (pageNum === 1) {
            scaleUsed.value = s;
          }
          const cssFudge = 2;
          const cssW = Math.ceil(viewport.width) + cssFudge;
          const cssH = Math.ceil(viewport.height) + cssFudge;

          const pageDiv = document.createElement("div");
          pageDiv.className = "page";
          pageDiv.style.width = `${cssW}px`;
          pageDiv.style.height = `${cssH}px`;
          pageDiv.id = `page-${pageNum}`;

          const canvas = document.createElement("canvas");
          const ctx = canvas.getContext("2d");
          const outputScale = window.devicePixelRatio || 1;
          const pixelW = Math.ceil(viewport.width * outputScale) + cssFudge * outputScale;
          const pixelH = Math.ceil(viewport.height * outputScale) + cssFudge * outputScale;
          canvas.width = pixelW;
          canvas.height = pixelH;
          canvas.style.width = `${cssW}px`;
          canvas.style.height = `${cssH}px`;
          pageDiv.appendChild(canvas);

          const textLayerDiv = document.createElement("div");
          textLayerDiv.className = "textLayer";
          pageDiv.style.setProperty("--scale-factor", String(viewport.scale));
          textLayerDiv.style.setProperty("--scale-factor", String(viewport.scale));
          container.style.setProperty("--scale-factor", String(viewport.scale));
          textLayerDiv.style.width = `${cssW}px`;
          textLayerDiv.style.height = `${cssH}px`;
          pageDiv.appendChild(textLayerDiv);

          container.appendChild(pageDiv);

          const transform = outputScale !== 1 ? [outputScale, 0, 0, outputScale, 0, 0] : null;
          const task = page.render({ canvasContext: ctx, viewport, transform });
          await task.promise;
          if (mySeq !== renderSeq) return;
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
        if (issues.value && issues.value.length) {
          try { highlightIssues(issues.value); } catch (e) { /* ignore */ }
        }
      }

      function rerender() { if (pdfDocVar) renderPDF(); }

      function zoomIn() {
        scaleMode.value = 'fixed';
        scale.value = Math.min(2.5, (scale.value || 1.0) + 0.1);
        rerender();
      }
      function zoomOut() {
        scaleMode.value = 'fixed';
        scale.value = Math.max(0.5, (scale.value || 1.0) - 0.1);
        rerender();
      }
      function zoomReset() {
        scaleMode.value = 'fixed';
        scale.value = 1.0;
        rerender();
      }
      function toggleFit() {
        scaleMode.value = (scaleMode.value === 'fit') ? 'fixed' : 'fit';
        rerender();
      }

      function normalizeWs(s) { return (s || "").replace(/\s+/g, " ").trim(); }

      function highlightIssues(list) {
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
                const idx = textNorm.indexOf(needleNorm);
                const raw = span.textContent;
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
                break;
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

      window.addEventListener('resize', () => {
        if (scaleMode.value === 'fit') rerender();
      });

      return { file, pdfBuffer, message, issues, summary, limits, loading, isDocx, onFileChange, analyze, scrollToPage, openGithub, zoomIn, zoomOut, zoomReset, toggleFit, scaleMode, scaleUsed };
    }
  };

  createApp(App).mount('#app');
})();

/* ── Tab switching ── */
document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    const panel = document.getElementById('tab-' + tab.dataset.tab);
    if (panel) panel.classList.add('active');

    // Clear the other file input when switching tabs so the form doesn't
    // accidentally submit the previous tab's file
    clearOtherInputs(tab.dataset.tab);
  });
});

function clearOtherInputs(active) {
  if (active !== 'upload') {
    const fi = document.getElementById('fileInput');
    if (fi) { fi.value = ''; }
    const fc = document.getElementById('fileChosen');
    if (fc) fc.textContent = '';
  }
  if (active !== 'image') {
    const fi = document.getElementById('fileInputImg');
    if (fi) { fi.value = ''; }
    const fc = document.getElementById('fileChosenImg');
    if (fc) fc.textContent = '';
    const pw = document.getElementById('imgPreviewWrap');
    if (pw) pw.style.display = 'none';
  }
  if (active !== 'paste') {
    // nothing to clear for textarea
  }
}

/* ── Char / word counter ── */
const textarea = document.getElementById('text');
const charCount = document.getElementById('charCount');
const wordCount = document.getElementById('wordCount');

if (textarea) {
  const update = () => {
    const val = textarea.value;
    if (charCount) charCount.textContent = val.length.toLocaleString();
    if (wordCount) wordCount.textContent = val.trim() ? val.trim().split(/\s+/).length.toLocaleString() : 0;
  };
  textarea.addEventListener('input', update);
}

/* ── Generic drop zone wiring ── */
function wireDropZone(zoneId, inputId, chosenId) {
  const zone   = document.getElementById(zoneId);
  const input  = document.getElementById(inputId);
  const chosen = document.getElementById(chosenId);
  if (!zone || !input) return;

  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      handleFileChosen(inputId, chosenId);
    }
  });
  input.addEventListener('change', () => handleFileChosen(inputId, chosenId));
}

function handleFileChosen(inputId, chosenId) {
  const input  = document.getElementById(inputId);
  const chosen = document.getElementById(chosenId);
  if (!input || !input.files.length) return;

  const file = input.files[0];
  if (chosen) chosen.textContent = '✅ ' + file.name;

  // Show image preview if it's the image input
  if (inputId === 'fileInputImg') {
    const previewWrap = document.getElementById('imgPreviewWrap');
    const preview     = document.getElementById('imgPreview');
    if (previewWrap && preview && file.type.startsWith('image/')) {
      const reader = new FileReader();
      reader.onload = e => {
        preview.src = e.target.result;
        previewWrap.style.display = 'flex';
      };
      reader.readAsDataURL(file);
    }
  }
}

wireDropZone('dropZone',    'fileInput',    'fileChosen');
wireDropZone('dropZoneImg', 'fileInputImg', 'fileChosenImg');

/* ── Animate risk meter on result page ── */
window.addEventListener('load', () => {
  const fill = document.querySelector('.risk-meter-fill');
  if (fill) {
    const target = fill.style.width;
    fill.style.width = '0%';
    setTimeout(() => { fill.style.width = target; }, 200);
  }
});

/* ── Submit button loading state ── */
const form      = document.getElementById('analyzeForm');
const submitBtn = document.getElementById('submitBtn');
if (form && submitBtn) {
  form.addEventListener('submit', (e) => {
    // Validate: at least one input must have content
    const pasteActive = document.getElementById('tab-paste')?.classList.contains('active');
    const text = document.getElementById('text')?.value.trim();
    const fileInput    = document.getElementById('fileInput');
    const fileInputImg = document.getElementById('fileInputImg');

    const hasText  = text && text.length > 0;
    const hasFile  = (fileInput?.files?.length > 0) || (fileInputImg?.files?.length > 0);

    if (!hasText && !hasFile) {
      e.preventDefault();
      alert('Please paste text or upload a file before analyzing.');
      return;
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="btn-icon">⏳</span> Analyzing…';
  });
}

/* ── Clause evidence toggle ── */
function toggleEvidence(btn) {
  const drawer = btn.nextElementSibling;
  if (!drawer) return;
  const isOpen = drawer.style.display !== 'none';
  drawer.style.display = isOpen ? 'none' : 'block';
  const count = drawer.querySelectorAll('.evidence-item').length;
  if (isOpen) {
    btn.textContent = btn.textContent.replace('Hide', 'Show');
  } else {
    btn.textContent = btn.textContent.replace('Show', 'Hide');
  }
}

/* ═══════════════════════════════════════
   COMPARE PAGE — tab switching
═══════════════════════════════════════ */
document.querySelectorAll('.ctab').forEach(tab => {
  tab.addEventListener('click', () => {
    const side = tab.dataset.side;
    const tabId = tab.dataset.tab;

    // Activate tab button
    document.querySelectorAll(`.ctab[data-side="${side}"]`)
      .forEach(t => t.classList.remove('active'));
    tab.classList.add('active');

    // Activate panel
    document.querySelectorAll(`[id="${side}-tab-paste"], [id="${side}-tab-upload"], [id="${side}-tab-image"]`)
      .forEach(p => p.classList.remove('active'));
    const panel = document.getElementById(`${side}-tab-${tabId}`);
    if (panel) panel.classList.add('active');
  });
});

/* ── Compare drop zones ── */
['left', 'right'].forEach(side => {
  // File drop zone
  wireCompareDrop(`${side}-drop-file`, `${side}-file-input`, `${side}-file-chosen`);
  // Image drop zone
  wireCompareDrop(`${side}-drop-img`, `${side}-img-input`, `${side}-img-chosen`,
    `${side}-img-preview`, `${side}-img-preview-wrap`);
});

function wireCompareDrop(zoneId, inputId, chosenId, previewId, previewWrapId) {
  const zone  = document.getElementById(zoneId);
  const input = document.getElementById(inputId);
  if (!zone || !input) return;

  zone.addEventListener('click', () => input.click());
  zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', e => {
    e.preventDefault(); zone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      onCompareFile(inputId, chosenId, previewId, previewWrapId);
    }
  });
  input.addEventListener('change', () => onCompareFile(inputId, chosenId, previewId, previewWrapId));
}

function onCompareFile(inputId, chosenId, previewId, previewWrapId) {
  const input  = document.getElementById(inputId);
  const chosen = document.getElementById(chosenId);
  if (!input || !input.files.length) return;
  const file = input.files[0];
  if (chosen) chosen.textContent = '✅ ' + file.name;

  if (previewId && previewWrapId && file.type.startsWith('image/')) {
    const reader = new FileReader();
    reader.onload = e => {
      const img  = document.getElementById(previewId);
      const wrap = document.getElementById(previewWrapId);
      if (img)  img.src = e.target.result;
      if (wrap) wrap.style.display = 'block';
    };
    reader.readAsDataURL(file);
  }
}

/* ── Compare form validation ── */
const compareForm = document.getElementById('compareForm');
const compareBtn  = document.getElementById('compareSubmitBtn');
if (compareForm && compareBtn) {
  compareForm.addEventListener('submit', e => {
    const leftText  = compareForm.querySelector('[name="left_text"]')?.value.trim();
    const rightText = compareForm.querySelector('[name="right_text"]')?.value.trim();
    const leftFile  = compareForm.querySelector('[name="left_file"]')?.files?.length > 0;
    const rightFile = compareForm.querySelector('[name="right_file"]')?.files?.length > 0;

    const hasLeft  = (leftText  && leftText.length  > 0) || leftFile;
    const hasRight = (rightText && rightText.length > 0) || rightFile;

    if (!hasLeft || !hasRight) {
      e.preventDefault();
      alert('Please provide content for both documents before comparing.');
      return;
    }
    compareBtn.disabled = true;
    compareBtn.innerHTML = '<span class="btn-icon">⏳</span> Comparing…';
  });
}

/* ═══════════════════════════════════════
   MULTI-COMPARE PAGE
═══════════════════════════════════════ */

// Track how many panels exist (starts at 3, rendered by Jinja)
let mcPanelCount = 3;
const MC_MAX = 8;

// Wire up the initial 3 panels on page load
document.addEventListener('DOMContentLoaded', () => {
  for (let i = 0; i < mcPanelCount; i++) wireMcPanel(i);
  updateAddButton();
});

/** Attach tab-switching and drop-zone behaviour to a panel by index */
function wireMcPanel(i) {
  // Tab switching
  document.querySelectorAll(`.mc-itab[data-index="${i}"]`).forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll(`.mc-itab[data-index="${i}"]`).forEach(t => t.classList.remove('active'));
      tab.classList.add('active');

      [`mc-${i}-paste`, `mc-${i}-file`, `mc-${i}-img`].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.remove('active');
      });
      const pane = document.getElementById(`mc-${i}-${tab.dataset.tab}`);
      if (pane) pane.classList.add('active');
    });
  });

  // File drop zones
  wireMcDrop(`mc-file-${i}`, `mc-file-chosen-${i}`);
  wireMcDrop(`mc-img-${i}`,  `mc-img-chosen-${i}`, true);
}

/** Wire a single drop zone — click-to-browse + drag-and-drop */
function wireMcDrop(inputId, chosenId, isImage = false) {
  const input = document.getElementById(inputId);
  if (!input) return;

  const zone = input.closest('.mc-drop');
  if (!zone) return;

  zone.addEventListener('click', () => input.click());

  zone.addEventListener('dragover', e => { e.preventDefault(); zone.style.borderColor = 'var(--gold)'; });
  zone.addEventListener('dragleave', () => zone.style.borderColor = '');
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.style.borderColor = '';
    if (e.dataTransfer.files.length) {
      input.files = e.dataTransfer.files;
      onMcFile(inputId, chosenId, isImage);
    }
  });

  input.addEventListener('change', () => onMcFile(inputId, chosenId, isImage));
}

function onMcFile(inputId, chosenId, isImage) {
  const input  = document.getElementById(inputId);
  const chosen = document.getElementById(chosenId);
  if (!input || !input.files.length) return;
  const file = input.files[0];
  if (chosen) {
    chosen.textContent = '✅ ' + file.name;
    chosen.style.color = 'var(--green)';
    chosen.style.fontSize = '0.78rem';
    chosen.style.marginTop = '6px';
  }
}

/** Dynamically add a new document panel (up to MC_MAX) */
function addPanel() {
  if (mcPanelCount >= MC_MAX) return;

  const template = document.getElementById('panelTemplate');
  if (!template) return;

  const i   = mcPanelCount;
  let html  = template.innerHTML
    .replaceAll('IDX', String(i))
    .replaceAll('NUM', String(i + 1));

  const wrapper = document.createElement('div');
  wrapper.innerHTML = html.trim();
  const panel = wrapper.firstElementChild;

  document.getElementById('mcPanels').appendChild(panel);
  wireMcPanel(i);

  mcPanelCount++;
  updateAddButton();

  // Smooth scroll to the new panel
  panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

/** Remove a panel and re-number remaining ones */
function removePanel(btn) {
  const panel = btn.closest('.mc-panel');
  if (!panel) return;

  // Don't allow going below 2 panels
  const allPanels = document.querySelectorAll('.mc-panel');
  if (allPanels.length <= 2) {
    panel.style.animation = 'shake 0.3s ease';
    setTimeout(() => panel.style.animation = '', 400);
    return;
  }

  panel.style.opacity = '0';
  panel.style.transform = 'scale(0.95)';
  panel.style.transition = 'all 0.2s ease';
  setTimeout(() => {
    panel.remove();
    mcPanelCount--;
    renumberPanels();
    updateAddButton();
  }, 200);
}

/** Renumber panel badges after a removal */
function renumberPanels() {
  document.querySelectorAll('.mc-panel').forEach((panel, idx) => {
    const badge = panel.querySelector('.mc-num');
    if (badge) badge.textContent = String(idx + 1);
    // Update data-index on tabs so wiring still works (important!)
    panel.querySelectorAll('.mc-itab').forEach(t => t.dataset.index = idx);
  });
}

/** Show/hide add button based on count */
function updateAddButton() {
  const btn  = document.getElementById('mcAddBtn');
  const note = document.getElementById('mcAddNote');
  if (!btn) return;
  const remaining = MC_MAX - mcPanelCount;
  if (mcPanelCount >= MC_MAX) {
    btn.disabled = true;
    btn.textContent = 'Maximum 8 documents reached';
    if (note) note.textContent = '';
  } else {
    btn.disabled = false;
    btn.textContent = '+ Add Another Document';
    if (note) note.textContent = `${remaining} slot${remaining !== 1 ? 's' : ''} remaining`;
  }
}

/* ── Leaderboard row expand/collapse ── */
function toggleLbDetail(btn) {
  const row    = btn.closest('.mc-lb-row');
  const detail = row ? row.querySelector('.mc-lb-detail') : null;
  if (!detail) return;

  const isOpen = detail.style.display !== 'none';
  detail.style.display = isOpen ? 'none' : 'flex';
  detail.style.flexDirection = 'column';
  btn.textContent = isOpen ? '▼' : '▲';
  btn.classList.toggle('open', !isOpen);
}

/* ── Multi-compare form validation ── */
const mcForm = document.getElementById('multiCompareForm');
const mcBtn  = document.getElementById('mcSubmitBtn');
if (mcForm && mcBtn) {
  mcForm.addEventListener('submit', e => {
    const panels  = document.querySelectorAll('.mc-panel');
    let filled = 0;

    panels.forEach(panel => {
      const idx       = panel.dataset.index;
      const hasText   = (panel.querySelector(`[name="doc_${idx}_text"]`)?.value || '').trim().length > 20;
      const hasFile   = (panel.querySelector(`[name="doc_${idx}_file"]`)?.files?.length || 0) > 0;
      if (hasText || hasFile) filled++;
    });

    if (filled < 2) {
      e.preventDefault();
      alert('Please provide content for at least 2 documents before ranking.');
      return;
    }

    mcBtn.disabled = true;
    mcBtn.innerHTML = `<span class="btn-icon">⏳</span> Analyzing ${filled} documents…`;
  });
}

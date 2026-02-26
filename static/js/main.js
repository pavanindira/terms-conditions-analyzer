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

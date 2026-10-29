let selectedGstFile = null;
let selectedErpFile = null;
let lastPipelineResponse = null;
let currentFilter = 'ALL';
let currentSortField = null; // 'date', 'gst_total', 'erp_total'
let currentSortOrder = 'asc'; // 'asc' or 'desc'
let currentVoucherData = null;
let currentNoticeData = null;
let currentAuditTrailList = null;
let activeSupplierFilter = null;
let lastRiskReport = null;
let currentSupplierSortField = null; // 'gstin', 'score', 'disputed'
let currentSupplierSortOrder = 'asc';
let lastGstHeaders = null;
let lastErpHeaders = null;
let lastPairwiseRole = null;
let isRoleValidationPending = false;

// Initialize Drag & Drop listeners
document.addEventListener('DOMContentLoaded', () => {
  setupDropzone('gstDropzone', 'gstFileInput', 'gst');
  setupDropzone('erpDropzone', 'erpFileInput', 'erp');
  checkApiHealth();
});

function checkApiHealth() {
  fetch('/health')
    .then(res => res.json())
    .then(data => {
      const badge = document.getElementById('apiStatusBadge');
      if (data.status === 'healthy') {
        badge.innerHTML = `<span class="status-dot green"></span><span class="status-text">API Online</span>`;
      }
    })
    .catch(() => {
      const badge = document.getElementById('apiStatusBadge');
      badge.innerHTML = `<span class="status-dot red" style="background:#f43f5e;"></span><span class="status-text" style="color:#f43f5e;">API Offline</span>`;
    });
}

function setupDropzone(dropzoneId, inputId, type) {
  const dropzone = document.getElementById(dropzoneId);
  const input = document.getElementById(inputId);

  dropzone.addEventListener('click', () => input.click());

  dropzone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropzone.classList.add('drag-over');
  });

  dropzone.addEventListener('dragleave', () => dropzone.classList.remove('drag-over'));

  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropzone.classList.remove('drag-over');
    if (e.dataTransfer.files.length > 0) {
      handleFileSelection(type, e.dataTransfer.files[0]);
    }
  });

  input.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
      handleFileSelection(type, e.target.files[0]);
    }
  });
}

function getFileIdentity(file) {
  if (!file) return null;
  return `${file.name}_${file.size}_${file.lastModified}`;
}

function validateSelectedFiles() {
  const errorContainer = document.getElementById('sameFileValidationError');
  const runBtn = document.getElementById('runReconcileBtn');

  if (!selectedGstFile || !selectedErpFile) {
    if (errorContainer) errorContainer.style.display = 'none';
    return false;
  }

  const gstId = getFileIdentity(selectedGstFile);
  const erpId = getFileIdentity(selectedErpFile);

  const isSameFile = (gstId === erpId);

  if (isSameFile) {
    if (errorContainer) {
      errorContainer.innerHTML = `
        <div style="display: flex; gap: 8px; align-items: center;">
          <i class="fa-solid fa-triangle-exclamation" style="font-size: 14px;"></i>
          <span><strong>Same-File Selection Error:</strong> GST and ERP files must be different. Please select two separate files.</span>
        </div>
      `;
      errorContainer.style.display = 'block';
    }
    if (runBtn) {
      runBtn.disabled = true;
      runBtn.style.opacity = '0.5';
      runBtn.style.cursor = 'not-allowed';
    }
    return true;
  } else {
    if (errorContainer) errorContainer.style.display = 'none';
    return false;
  }
}

async function fetchPairwiseSourceRole(gstCols, erpCols) {
  if (!gstCols || !erpCols || gstCols.length === 0 || erpCols.length === 0) {
    return { gst_role: 'AMBIGUOUS', erp_role: 'AMBIGUOUS', assignment_valid: true, confidence: 0.5, reasoning: 'Insufficient column data' };
  }

  try {
    const res = await fetch('/api/v1/ai/detect-source-role', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ gst_columns: gstCols, erp_columns: erpCols })
    });

    if (!res.ok) {
      console.warn('Source role detection endpoint returned status:', res.status);
      return { gst_role: 'AMBIGUOUS', erp_role: 'AMBIGUOUS', assignment_valid: true, confidence: 0.5, reasoning: 'Role detection service unavailable' };
    }

    return await res.json();
  } catch (err) {
    console.error('Source role detection error:', err.message);
    return { gst_role: 'AMBIGUOUS', erp_role: 'AMBIGUOUS', assignment_valid: true, confidence: 0.5, reasoning: err.message };
  }
}

function validateFileSourceRoles() {
  const roleContainer = document.getElementById('fileRoleValidationError');

  if (isRoleValidationPending) {
    if (roleContainer) {
      roleContainer.className = 'role-validation-box role-info-box';
      roleContainer.style.background = '#f0f9ff';
      roleContainer.style.border = '1px solid #bae6fd';
      roleContainer.style.color = '#0284c7';
      roleContainer.style.padding = '12px 16px';
      roleContainer.style.borderRadius = 'var(--radius-sm)';
      roleContainer.style.margin = '16px 0';
      roleContainer.style.fontSize = '13px';
      roleContainer.style.lineHeight = '1.5';
      roleContainer.innerHTML = `
        <div style="display: flex; gap: 8px; align-items: center;">
          <i class="fa-solid fa-spinner fa-spin" style="font-size: 14px;"></i>
          <span>Evaluating file source roles via Gemini AI Gateway...</span>
        </div>
      `;
      roleContainer.style.display = 'block';
    }
    return { isBlock: true, isWarning: false, isPending: true };
  }
  
  if (!lastPairwiseRole || !selectedGstFile || !selectedErpFile) {
    if (roleContainer) roleContainer.style.display = 'none';
    return { isBlock: false, isWarning: false, isPending: false };
  }

  const gstRole = lastPairwiseRole.gst_role;
  const erpRole = lastPairwiseRole.erp_role;
  const assignmentValid = lastPairwiseRole.assignment_valid;

  // Case 1: Swapped assignment or invalid assignment
  const isSwapped = (!assignmentValid) || (gstRole === 'ERP_LIKELY' && erpRole === 'GST_LIKELY');

  if (isSwapped) {
    if (roleContainer) {
      roleContainer.className = 'role-validation-box role-block-box';
      roleContainer.style.background = '#fff5f5';
      roleContainer.style.border = '1px solid #fed7d7';
      roleContainer.style.color = '#c53030';
      roleContainer.style.padding = '12px 16px';
      roleContainer.style.borderRadius = 'var(--radius-sm)';
      roleContainer.style.margin = '16px 0';
      roleContainer.style.fontSize = '13px';
      roleContainer.style.lineHeight = '1.5';
      roleContainer.innerHTML = `
        <div style="display: flex; gap: 8px; align-items: flex-start;">
          <i class="fa-solid fa-circle-xmark" style="margin-top: 3px; font-size: 14px;"></i>
          <div>
            <strong style="display: block; margin-bottom: 2px;">❌ File Assignment Error</strong>
            <span>The selected <strong>GST file</strong> appears to contain ERP-style columns, while the selected <strong>ERP file</strong> appears to contain GST Portal columns (AI reasoning: "${escapeHtml(lastPairwiseRole.reasoning)}"). Please swap the selected files and try again.</span>
          </div>
        </div>
      `;
      roleContainer.style.display = 'block';
    }
    return { isBlock: true, isWarning: false, isPending: false };
  }

  // Case 2: One-sided mismatch warning
  const isOneSidedMismatch = (gstRole === 'ERP_LIKELY') || (erpRole === 'GST_LIKELY');
  
  if (isOneSidedMismatch) {
    if (roleContainer) {
      let warnMessage = '';
      if (gstRole === 'ERP_LIKELY') {
        warnMessage = `The selected <strong>GST input file</strong> contains ERP-style column signatures (${escapeHtml(lastPairwiseRole.reasoning)}). Please verify your file assignment.`;
      } else {
        warnMessage = `The selected <strong>ERP input file</strong> contains GST Portal-style column signatures (${escapeHtml(lastPairwiseRole.reasoning)}). Please verify your file assignment.`;
      }

      roleContainer.className = 'role-validation-box role-warn-box';
      roleContainer.style.background = '#fffbe6';
      roleContainer.style.border = '1px solid #ffe58f';
      roleContainer.style.color = '#d46b08';
      roleContainer.style.padding = '12px 16px';
      roleContainer.style.borderRadius = 'var(--radius-sm)';
      roleContainer.style.margin = '16px 0';
      roleContainer.style.fontSize = '13px';
      roleContainer.style.lineHeight = '1.5';
      roleContainer.innerHTML = `
        <div style="display: flex; gap: 8px; align-items: flex-start;">
          <i class="fa-solid fa-triangle-exclamation" style="margin-top: 3px; font-size: 14px;"></i>
          <div>
            <strong style="display: block; margin-bottom: 2px;">⚠️ Role Verification Warning</strong>
            <span>${warnMessage}</span>
          </div>
        </div>
      `;
      roleContainer.style.display = 'block';
    }
    return { isBlock: false, isWarning: true, isPending: false };
  }

  // Case 3: Correct or Ambiguous -> Hide validation container
  if (roleContainer) {
    roleContainer.style.display = 'none';
    roleContainer.innerHTML = '';
  }
  return { isBlock: false, isWarning: false, isPending: false };
}

async function handleFileSelection(type, file) {
  if (type === 'gst') {
    selectedGstFile = file;
    document.getElementById('gstFileName').innerText = file.name;
    document.getElementById('gstFileInfo').style.display = 'inline-flex';
  } else {
    selectedErpFile = file;
    document.getElementById('erpFileName').innerText = file.name;
    document.getElementById('erpFileInfo').style.display = 'inline-flex';
  }

  validateSelectedFiles();

  if (selectedGstFile && selectedErpFile) {
    await fetchAndRenderColumnMappings();
  }
}

function removeFile(type) {
  if (type === 'gst') {
    selectedGstFile = null;
    lastGstHeaders = null;
    lastPairwiseRole = null;
    document.getElementById('gstFileInput').value = '';
    document.getElementById('gstFileInfo').style.display = 'none';
  } else {
    selectedErpFile = null;
    lastErpHeaders = null;
    lastPairwiseRole = null;
    document.getElementById('erpFileInput').value = '';
    document.getElementById('erpFileInfo').style.display = 'none';
  }

  validateSelectedFiles();
  validateFileSourceRoles();

  document.getElementById('mappingPanel').style.display = 'none';
  document.getElementById('configBar').style.display = 'none';
}

function updateToleranceLabel(val) {
  document.getElementById('toleranceValDisplay').innerText = `₹${parseFloat(val).toFixed(2)}`;
}

function setStepState(stepId, state) {
  const step = document.getElementById(`step-${stepId}`);
  if (!step) return;
  const icon = step.querySelector('.step-icon');
  
  step.classList.remove('active', 'completed');
  if (state === 'active') {
    step.classList.add('active');
    icon.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i>`;
  } else if (state === 'completed') {
    step.classList.add('completed');
    icon.innerHTML = `<i class="fa-solid fa-circle-check"></i>`;
  } else {
    icon.innerHTML = `<i class="fa-regular fa-circle"></i>`;
  }
}

const CANONICAL_FIELD_LABELS = {
  gstin: "Supplier GSTIN",
  invoice_number: "Invoice Number",
  invoice_date: "Invoice Date",
  taxable_value: "Taxable Value (INR)",
  cgst: "CGST Amount",
  sgst: "SGST Amount",
  igst: "IGST Amount",
  total_invoice_value: "Total Invoice Value"
};

const CANONICAL_FIELD_TYPES = {
  gstin: "Text",
  invoice_number: "Text",
  invoice_date: "Date",
  taxable_value: "Numeric",
  cgst: "Numeric",
  sgst: "Numeric",
  igst: "Numeric",
  total_invoice_value: "Numeric"
};

async function fetchAndRenderColumnMappings() {
  const mappingPanel = document.getElementById('mappingPanel');
  const configBar = document.getElementById('configBar');

  mappingPanel.style.display = 'block';
  document.getElementById('gstMappingTableBody').innerHTML = `<tr><td colspan="3" style="text-align:center;"><i class="fa-solid fa-spinner fa-spin"></i> Analyzing GST columns...</td></tr>`;
  document.getElementById('erpMappingTableBody').innerHTML = `<tr><td colspan="3" style="text-align:center;"><i class="fa-solid fa-spinner fa-spin"></i> Analyzing ERP columns...</td></tr>`;

  isRoleValidationPending = true;
  lastPairwiseRole = null;
  validateColumnMappings();

  try {
    const uploadGstPromise = uploadFileForIngestion(selectedGstFile);
    const uploadErpPromise = uploadFileForIngestion(selectedErpFile);

    const [gstIngest, erpIngest] = await Promise.all([uploadGstPromise, uploadErpPromise]);

    const gstCols = gstIngest.metadata.columns;
    const erpCols = erpIngest.metadata.columns;

    lastGstHeaders = gstCols;
    lastErpHeaders = erpCols;

    const gstMappingsPromise = detectMappings(gstCols);
    const erpMappingsPromise = detectMappings(erpCols);
    const pairRolePromise = fetchPairwiseSourceRole(gstCols, erpCols);

    const [gstMappings, erpMappings, pairRoleResp] = await Promise.all([
      gstMappingsPromise,
      erpMappingsPromise,
      pairRolePromise
    ]);

    lastPairwiseRole = pairRoleResp;
    isRoleValidationPending = false;

    renderMappingTable('gst', gstCols, gstMappings.mappings);
    renderMappingTable('erp', erpCols, erpMappings.mappings);

    validateColumnMappings();

    configBar.style.display = 'flex';
    configBar.scrollIntoView({ behavior: 'smooth' });

  } catch (err) {
    isRoleValidationPending = false;
    alert(`Failed to analyze uploaded files for mapping: ${err.message}`);
    mappingPanel.style.display = 'none';
    configBar.style.display = 'none';
    validateColumnMappings();
  }
}

async function uploadFileForIngestion(file) {
  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch('/api/v1/ingestion/upload', {
    method: 'POST',
    body: formData
  });

  if (!res.ok) {
    const errData = await res.json();
    throw new Error(errData.detail?.message || 'Ingestion failed');
  }
  return res.json();
}

async function detectMappings(columns) {
  const res = await fetch('/api/v1/mapping/detect', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ columns: columns, enable_ai: true })
  });

  if (!res.ok) {
    throw new Error('Mapping detection API error');
  }
  return res.json();
}

function renderMappingTable(type, allColumns, mappings) {
  const tbody = document.getElementById(`${type}MappingTableBody`);
  tbody.innerHTML = '';

  mappings.forEach(m => {
    const tr = document.createElement('tr');
    tr.id = `map-row-${type}-${m.canonical_field}`;

    updateRowWarningClass(tr, m.method, m.confidence);

    const label = CANONICAL_FIELD_LABELS[m.canonical_field] || m.canonical_field;
    const typeLabel = CANONICAL_FIELD_TYPES[m.canonical_field] || 'Text';

    let selectHtml = `<select class="mapping-select" data-field="${m.canonical_field}" onchange="onMappingChange('${type}', '${m.canonical_field}', this)">`;
    selectHtml += `<option value="">-- Unmapped --</option>`;
    allColumns.forEach(col => {
      const selected = col === m.source_column ? 'selected' : '';
      selectHtml += `<option value="${escapeHtml(col)}" ${selected}>${escapeHtml(col)}</option>`;
    });
    selectHtml += `</select>`;

    const badgeHtml = getMappingBadgeHtml(m.method, m.confidence);

    tr.innerHTML = `
      <td>
        <strong>${label}</strong>
        <div style="font-size: 10.5px; color: var(--text-dim); font-weight: normal; margin-top: 2px;">Type: ${typeLabel}</div>
      </td>
      <td>${selectHtml}</td>
      <td class="badge-col">${badgeHtml}</td>
    `;
    tbody.appendChild(tr);
  });
}

function updateRowWarningClass(tr, method, confidence) {
  tr.classList.remove('mapping-row-low', 'mapping-row-unmapped');
  if (method === 'UNMAPPED') {
    tr.classList.add('mapping-row-unmapped');
  } else if (method === 'AI_SUGGESTED' && confidence < 0.85) {
    tr.classList.add('mapping-row-low');
  }
}

function getMappingBadgeHtml(method, confidence) {
  if (method === 'DETERMINISTIC') {
    return `<span class="map-badge map-badge-det"><i class="fa-solid fa-circle-check"></i> Deterministic</span>`;
  } else if (method === 'AI_SUGGESTED') {
    return `<span class="map-badge map-badge-ai"><i class="fa-solid fa-wand-magic-sparkles"></i> AI (${Math.round(confidence * 100)}%)</span>`;
  } else {
    return `<span class="map-badge map-badge-unmapped"><i class="fa-solid fa-triangle-exclamation"></i> Unmapped</span>`;
  }
}

function onMappingChange(type, canonicalField, selectElem) {
  const tr = document.getElementById(`map-row-${type}-${canonicalField}`);
  const badgeCol = tr.querySelector('.badge-col');
  const val = selectElem.value;

  if (val === '') {
    updateRowWarningClass(tr, 'UNMAPPED', 0.0);
    badgeCol.innerHTML = getMappingBadgeHtml('UNMAPPED', 0.0);
  } else {
    updateRowWarningClass(tr, 'DETERMINISTIC', 1.0);
    badgeCol.innerHTML = getMappingBadgeHtml('DETERMINISTIC', 1.0);
  }

  validateColumnMappings();
}

function validateColumnMappings() {
  const errorContainer = document.getElementById('mappingValidationError');
  const runBtn = document.getElementById('runReconcileBtn');
  if (!errorContainer || !runBtn) return;

  const gstMapping = {};
  const gstColsMapped = [];
  const gstDuplicates = new Set();

  document.querySelectorAll('#gstMappingTableBody select').forEach(select => {
    const val = select.value;
    const field = select.dataset.field;
    if (val) {
      if (gstColsMapped.includes(val)) {
        gstDuplicates.add(val);
      }
      gstColsMapped.push(val);
      gstMapping[field] = val;
    }
  });

  const erpMapping = {};
  const erpColsMapped = [];
  const erpDuplicates = new Set();

  document.querySelectorAll('#erpMappingTableBody select').forEach(select => {
    const val = select.value;
    const field = select.dataset.field;
    if (val) {
      if (erpColsMapped.includes(val)) {
        erpDuplicates.add(val);
      }
      erpColsMapped.push(val);
      erpMapping[field] = val;
    }
  });

  const errors = [];

  // Check mandatory GST
  if (!gstMapping.gstin || !gstMapping.invoice_number) {
    errors.push('GSTR-2B Mapping: <strong>Supplier GSTIN</strong> and <strong>Invoice Number</strong> are required fields.');
  }
  // Check duplicates GST
  if (gstDuplicates.size > 0) {
    errors.push(`GSTR-2B Mapping: Column duplication detected (duplicate: ${Array.from(gstDuplicates).map(x => `'${x}'`).join(', ')}). Each column can only be mapped to one field.`);
  }

  // Check mandatory ERP
  if (!erpMapping.gstin || !erpMapping.invoice_number) {
    errors.push('ERP Mapping: <strong>Supplier GSTIN</strong> and <strong>Invoice Number</strong> are required fields.');
  }
  // Check duplicates ERP
  if (erpDuplicates.size > 0) {
    errors.push(`ERP Mapping: Column duplication detected (duplicate: ${Array.from(erpDuplicates).map(x => `'${x}'`).join(', ')}). Each column can only be mapped to one field.`);
  }

  const isSameFile = validateSelectedFiles();
  const roleStatus = validateFileSourceRoles();

  if (errors.length > 0) {
    errorContainer.innerHTML = `
      <div style="display: flex; gap: 8px; align-items: flex-start;">
        <i class="fa-solid fa-triangle-exclamation" style="margin-top: 3px; font-size: 14px;"></i>
        <div>
          <strong style="display: block; margin-bottom: 4px;">Mapping Validation Issues:</strong>
          <ul style="margin: 0; padding-left: 16px;">
            ${errors.map(err => `<li style="margin-bottom: 2px;">${err}</li>`).join('')}
          </ul>
        </div>
      </div>
    `;
    errorContainer.style.display = 'block';
  } else {
    errorContainer.style.display = 'none';
    errorContainer.innerHTML = '';
  }

  const canRun = !isSameFile && !roleStatus.isBlock && (errors.length === 0);

  if (!canRun) {
    runBtn.disabled = true;
    runBtn.style.opacity = '0.5';
    runBtn.style.cursor = 'not-allowed';
  } else {
    runBtn.disabled = false;
    runBtn.style.opacity = '1';
    runBtn.style.cursor = 'pointer';
  }
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}

async function executeReconciliation() {
  if (!selectedGstFile || !selectedErpFile) {
    alert('Please upload both a GST Portal dataset and an ERP Purchase Register file before running reconciliation.');
    return;
  }

  const isSameFile = validateSelectedFiles();
  if (isSameFile) {
    alert('Same-file selection error: The same physical file was selected for both GST and ERP. Please select two distinct files.');
    return;
  }

  const roleStatus = validateFileSourceRoles();
  if (roleStatus.isBlock) {
    if (roleStatus.isPending) {
      alert('File source role verification is still in progress. Please wait for evaluation to finish.');
    } else {
      alert('File assignment error: The selected GST and ERP files appear to be swapped. Please swap the selected files and try again.');
    }
    return;
  }

  // Retrieve column mappings from selectors
  const gstMapping = {};
  document.querySelectorAll('#gstMappingTableBody select').forEach(select => {
    if (select.value) {
      gstMapping[select.dataset.field] = select.value;
    }
  });

  const erpMapping = {};
  document.querySelectorAll('#erpMappingTableBody select').forEach(select => {
    if (select.value) {
      erpMapping[select.dataset.field] = select.value;
    }
  });

  // Verify mandatory mappings
  if (!gstMapping.gstin || !gstMapping.invoice_number) {
    alert('GST Portal Mapping Error: Please map "Supplier GSTIN" and "Invoice Number" before executing reconciliation.');
    return;
  }
  if (!erpMapping.gstin || !erpMapping.invoice_number) {
    alert('ERP Register Mapping Error: Please map "Supplier GSTIN" and "Invoice Number" before executing reconciliation.');
    return;
  }

  const btn = document.getElementById('runReconcileBtn');
  const originalBtnHtml = btn.innerHTML;
  btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processing...`;
  btn.disabled = true;

  const overlay = document.getElementById('scannerOverlay');
  overlay.style.display = 'flex';

  setStepState('ingest', 'active');
  setStepState('normalize', 'pending');
  setStepState('match', 'pending');
  setStepState('ai', 'pending');
  setStepState('scoring', 'pending');

  const formData = new FormData();
  formData.append('gst_file', selectedGstFile);
  formData.append('erp_file', selectedErpFile);
  formData.append('gst_mapping', JSON.stringify(gstMapping));
  formData.append('erp_mapping', JSON.stringify(erpMapping));

  const includeAi = document.getElementById('aiReviewToggle').checked;

  const apiPromise = fetch(`/api/v1/orchestration/reconcile-files?include_ai_reviews=${includeAi}`, {
    method: 'POST',
    body: formData,
  }).then(async (response) => {
    if (!response.ok) {
      const errData = await response.json();
      throw new Error(errData.detail?.message || 'Server error');
    }
    return response.json();
  });

  const runAnimation = async () => {
    await new Promise(r => setTimeout(r, 350));
    setStepState('ingest', 'completed');
    setStepState('normalize', 'active');

    await new Promise(r => setTimeout(r, 350));
    setStepState('normalize', 'completed');
    setStepState('match', 'active');

    await new Promise(r => setTimeout(r, 350));
    setStepState('match', 'completed');
    setStepState('ai', 'active');

    await new Promise(r => setTimeout(r, 350));
    setStepState('ai', 'completed');
    setStepState('scoring', 'active');

    await new Promise(r => setTimeout(r, 350));
  };

  try {
    const [data] = await Promise.all([apiPromise, runAnimation()]);
    setStepState('scoring', 'completed');
    await new Promise(r => setTimeout(r, 200));

    lastPipelineResponse = data;

    renderDashboard(data);
    renderResultsTable(data.results);

    const resetBtn = document.getElementById('startNewReconcileBtn');
    if (resetBtn) resetBtn.style.display = 'inline-flex';

    document.getElementById('dashboardPanel').style.display = 'block';
    document.getElementById('resultsPanel').style.display = 'block';
    document.getElementById('resultsPanel').scrollIntoView({ behavior: 'smooth' });

  } catch (err) {
    alert(`Reconciliation failed: ${err.message}`);
  } finally {
    overlay.style.display = 'none';
    btn.innerHTML = originalBtnHtml;
    btn.disabled = false;
  }
}

function renderDashboard(data) {
  const report = data.report_analytics;

  document.getElementById('matchRateVal').innerText = `${report.match_rate_percentage.toFixed(1)}%`;
  document.getElementById('exactMatchSub').innerText = `${report.exact_matches_count} Exact / ${report.partial_matches_count} Partial`;

  document.getElementById('claimableItcVal').innerText = `₹${report.itc_claimable_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  document.getElementById('disputedItcVal').innerText = `₹${report.itc_disputed_amount.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  document.getElementById('manualReviewVal').innerText = report.manual_reviews_required_count;

  // Counts for tabs
  const results = data.results;
  document.getElementById('countAll').innerText = results.length;
  document.getElementById('countExact').innerText = results.filter(r => r.classification === 'EXACT_MATCH').length;
  document.getElementById('countPartial').innerText = results.filter(r => r.classification === 'PARTIAL_MATCH').length;
  document.getElementById('countDiscrepancy').innerText = results.filter(r => r.classification === 'DISCREPANCY').length;
  document.getElementById('countUnmatched').innerText = results.filter(r => r.classification === 'UNMATCHED').length;

  fetchVendorRiskAnalytics(data);
}

async function fetchVendorRiskAnalytics(data) {
  try {
    const response = await fetch('/api/v1/orchestration/vendor-risk-analytics', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        summary: data.batch_summary,
        results: data.results,
      }),
    });

    if (!response.ok) return;
    const riskReport = await response.json();
    lastRiskReport = riskReport;
    renderVendorRiskTable(riskReport);
  } catch (err) {
    console.error('Vendor risk evaluation failed:', err);
  }
}

function renderVendorRiskTable(report) {
  const container = document.getElementById('vendorRiskContainer');
  const tbody = document.getElementById('vendorRiskTableBody');
  const summaryBadge = document.getElementById('vendorRiskSummaryBadge');

  if (!report || !report.vendor_profiles || report.vendor_profiles.length === 0) {
    container.style.display = 'none';
    return;
  }

  summaryBadge.innerText = `${report.high_risk_vendors_count} High-Risk Supplier(s)`;
  tbody.innerHTML = '';

  let profiles = [...report.vendor_profiles];

  // 1. Search Filter (by GSTIN)
  const searchQuery = (document.getElementById('supplierSearchInput')?.value || '').trim().toLowerCase();
  if (searchQuery) {
    profiles = profiles.filter(p => p.gstin.toLowerCase().includes(searchQuery));
  }

  // 2. Risk Level Filter
  const riskFilter = document.getElementById('supplierRiskFilter')?.value || 'ALL';
  if (riskFilter !== 'ALL') {
    profiles = profiles.filter(p => p.risk_category === riskFilter);
  }

  // 3. Risk Table Sorting
  if (currentSupplierSortField === 'gstin') {
    profiles.sort((a, b) => {
      const cmp = a.gstin.localeCompare(b.gstin);
      return currentSupplierSortOrder === 'asc' ? cmp : -cmp;
    });
  } else if (currentSupplierSortField === 'disputed') {
    profiles.sort((a, b) => {
      const cmp = a.disputed_itc_amount - b.disputed_itc_amount;
      return currentSupplierSortOrder === 'asc' ? cmp : -cmp;
    });
  } else if (currentSupplierSortField === 'score') {
    profiles.sort((a, b) => {
      const cmp = a.compliance_score - b.compliance_score;
      return currentSupplierSortOrder === 'asc' ? cmp : -cmp;
    });
  }

  if (profiles.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="10" style="text-align: center; color: var(--text-dim); padding: 24px;">
          No supplier profiles match the filter.
        </td>
      </tr>
    `;
    container.style.display = 'block';
    return;
  }

  profiles.forEach(p => {
    const tr = document.createElement('tr');
    tr.style.cursor = 'pointer';
    if (activeSupplierFilter === p.gstin) {
      tr.style.background = 'rgba(99, 102, 241, 0.08)';
      tr.style.borderLeft = '3px solid var(--primary)';
    }

    let catClass = 'badge-exact';
    if (p.risk_category === 'MEDIUM_RISK') catClass = 'badge-partial';
    if (p.risk_category === 'HIGH_RISK') catClass = 'badge-discrepancy';

    const secWarn = p.section_16_4_warning 
      ? `<span class="review-flag" style="color:var(--rose);"><i class="fa-solid fa-triangle-exclamation"></i> Forfeiture Risk</span>` 
      : `<span style="color:var(--emerald);"><i class="fa-solid fa-check"></i> Safe</span>`;

    tr.onclick = (e) => {
      if (e.target.closest('button')) return;
      selectSupplierFilter(p.gstin, tr);
    };

    tr.innerHTML = `
      <td><strong>${p.gstin}</strong></td>
      <td>${p.total_invoices}</td>
      <td style="color: var(--emerald); font-weight: 600;">${p.exact_matches}</td>
      <td style="color: var(--amber); font-weight: 600;">${p.discrepancies}</td>
      <td style="color: var(--rose); font-weight: 600;">${p.unmatched}</td>
      <td style="color: var(--rose); font-weight: 600;">₹${p.disputed_itc_amount.toLocaleString('en-IN', {minimumFractionDigits: 2})}</td>
      <td>
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="font-weight:700; width: 45px;">${p.compliance_score.toFixed(1)}%</span>
          <div style="flex: 1; height: 6px; background: #e2e8f0; border-radius: 3px; min-width: 50px; max-width: 80px; overflow: hidden;">
            <div style="width: ${p.compliance_score}%; height: 100%; background: ${p.compliance_score >= 85 ? 'var(--emerald)' : (p.compliance_score >= 50 ? 'var(--amber)' : 'var(--rose)')}; border-radius: 3px;"></div>
          </div>
        </div>
      </td>
      <td><span class="badge ${catClass}">${p.risk_category}</span></td>
      <td>${secWarn}</td>
      <td style="text-align: center;">
        <button type="button" class="btn secondary-btn" style="padding: 3px 8px; font-size: 11px; display: inline-flex; align-items: center; gap: 4px;" onclick="showSupplierRiskDetails('${p.gstin}')">
          <i class="fa-solid fa-eye"></i> Details
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });

  container.style.display = 'block';
}

function onSupplierSearchOrFilterChange() {
  if (lastRiskReport) {
    renderVendorRiskTable(lastRiskReport);
  }
}

function toggleSupplierSort(field) {
  if (currentSupplierSortField === field) {
    currentSupplierSortOrder = currentSupplierSortOrder === 'asc' ? 'desc' : 'asc';
  } else {
    currentSupplierSortField = field;
    currentSupplierSortOrder = 'asc';
  }
  updateSupplierSortIcons();
  if (lastRiskReport) {
    renderVendorRiskTable(lastRiskReport);
  }
}

function updateSupplierSortIcons() {
  const fields = ['gstin', 'disputed', 'score'];
  fields.forEach(field => {
    const el = document.getElementById(`supplier-sort-icon-${field}`);
    if (!el) return;
    if (currentSupplierSortField === field) {
      if (currentSupplierSortOrder === 'asc') {
        el.innerHTML = `<i class="fa-solid fa-sort-up" style="color: var(--primary);"></i>`;
      } else {
        el.innerHTML = `<i class="fa-solid fa-sort-down" style="color: var(--primary);"></i>`;
      }
    } else {
      el.innerHTML = `<i class="fa-solid fa-sort" style="color: var(--text-dim); opacity: 0.4;"></i>`;
    }
  });
}

function selectSupplierFilter(gstin, trElement) {
  if (activeSupplierFilter === gstin) {
    clearSupplierFilter();
    return;
  }

  activeSupplierFilter = gstin;

  const badge = document.getElementById('activeSupplierFilterBadge');
  const gstinText = document.getElementById('activeSupplierFilterGstin');
  if (badge && gstinText) {
    gstinText.innerText = gstin;
    badge.style.display = 'flex';
  }

  if (lastRiskReport) {
    renderVendorRiskTable(lastRiskReport);
  }

  if (lastPipelineResponse) {
    renderResultsTable(lastPipelineResponse.results);
    document.getElementById('resultsPanel')?.scrollIntoView({ behavior: 'smooth' });
  }
}

function clearSupplierFilter() {
  activeSupplierFilter = null;
  const badge = document.getElementById('activeSupplierFilterBadge');
  if (badge) badge.style.display = 'none';

  if (lastRiskReport) {
    renderVendorRiskTable(lastRiskReport);
  }

  if (lastPipelineResponse) {
    renderResultsTable(lastPipelineResponse.results);
  }
}

function showSupplierRiskDetails(gstin) {
  if (!lastRiskReport || !lastPipelineResponse) return;

  const profile = lastRiskReport.vendor_profiles.find(p => p.gstin === gstin);
  if (!profile) return;

  const riskInvoices = lastPipelineResponse.results.filter(r => {
    const rowGstin = r.gst_record?.gstin || r.erp_record?.gstin || '';
    return rowGstin === gstin && r.classification !== 'EXACT_MATCH';
  });

  const modalBody = document.getElementById('modalBody');
  if (!modalBody) return;

  let invoicesHtml = '<p style="color: var(--emerald); font-size: 13px;"><i class="fa-solid fa-circle-check"></i> All invoices matched perfectly. Supplier compliance is 100%.</p>';
  if (riskInvoices.length > 0) {
    invoicesHtml = `
      <table style="width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 10px;">
        <thead>
          <tr style="border-bottom: 1px solid var(--border-card); text-align: left; color: var(--text-muted);">
            <th style="padding: 6px;">Invoice #</th>
            <th style="padding: 6px;">Date</th>
            <th style="padding: 6px;">GST Total</th>
            <th style="padding: 6px;">ERP Total</th>
            <th style="padding: 6px;">Classification</th>
          </tr>
        </thead>
        <tbody>
          ${riskInvoices.map(r => {
            const invNo = r.gst_record?.invoice_number || r.erp_record?.invoice_number || '-';
            const invDate = r.gst_record?.invoice_date || r.erp_record?.invoice_date || '-';
            const gstVal = r.gst_record ? `₹${r.gst_record.total_invoice_value.toFixed(2)}` : '-';
            const erpVal = r.erp_record ? `₹${r.erp_record.total_invoice_value.toFixed(2)}` : '-';

            let badgeClass = 'badge-partial';
            if (r.classification === 'DISCREPANCY') badgeClass = 'badge-discrepancy';
            if (r.classification === 'UNMATCHED') badgeClass = 'badge-unmatched';

            return `
              <tr style="border-bottom: 1px solid rgba(0,0,0,0.04);">
                <td style="padding: 6px; font-weight: 600;">${invNo}</td>
                <td style="padding: 6px;">${invDate}</td>
                <td style="padding: 6px; color: var(--emerald);">${gstVal}</td>
                <td style="padding: 6px; color: var(--cyan);">${erpVal}</td>
                <td style="padding: 6px;"><span class="badge ${badgeClass}">${r.classification}</span></td>
              </tr>
            `;
          }).join('')}
        </tbody>
      </table>
    `;
  }

  let catClass = 'badge-exact';
  if (profile.risk_category === 'MEDIUM_RISK') catClass = 'badge-partial';
  if (profile.risk_category === 'HIGH_RISK') catClass = 'badge-discrepancy';

  modalBody.innerHTML = `
    <div style="background: #f8fafc; border: 1px solid var(--border-card); padding: 16px; border-radius: 8px; margin-bottom: 16px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <h3 style="font-size: 16px; margin: 0; color: var(--text-main); font-weight: 700;">Supplier Profile: ${gstin}</h3>
        <span class="badge ${catClass}">${profile.risk_category}</span>
      </div>

      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 10px; font-size: 13px;">
        <div>
          <span style="color: var(--text-muted); display: block; font-size: 11px; margin-bottom: 2px;">Compliance Score</span>
          <strong style="font-size: 15px; color: ${profile.compliance_score >= 85 ? 'var(--emerald)' : (profile.compliance_score >= 50 ? 'var(--amber)' : 'var(--rose)')}">${profile.compliance_score.toFixed(1)}%</strong>
        </div>
        <div>
          <span style="color: var(--text-muted); display: block; font-size: 11px; margin-bottom: 2px;">Total Invoices</span>
          <strong style="font-size: 15px; color: var(--text-main);">${profile.total_invoices}</strong>
        </div>
        <div>
          <span style="color: var(--text-muted); display: block; font-size: 11px; margin-bottom: 2px;">Exact Matches</span>
          <strong style="font-size: 15px; color: var(--emerald);">${profile.exact_matches}</strong>
        </div>
        <div>
          <span style="color: var(--text-muted); display: block; font-size: 11px; margin-bottom: 2px;">Discrepancies</span>
          <strong style="font-size: 15px; color: var(--amber);">${profile.discrepancies}</strong>
        </div>
        <div>
          <span style="color: var(--text-muted); display: block; font-size: 11px; margin-bottom: 2px;">Unmatched</span>
          <strong style="font-size: 15px; color: var(--rose);">${profile.unmatched}</strong>
        </div>
        <div>
          <span style="color: var(--text-muted); display: block; font-size: 11px; margin-bottom: 2px;">Disputed ITC</span>
          <strong style="font-size: 15px; color: var(--rose);">₹${profile.disputed_itc_amount.toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong>
        </div>
      </div>
    </div>

    <div class="modal-section">
      <h4 style="font-size: 13.5px; color: var(--text-main); font-weight: 700; margin-bottom: 6px;"><i class="fa-solid fa-triangle-exclamation" style="color: var(--rose);"></i> Invoices Impacting Risk Score</h4>
      <div style="max-height: 250px; overflow-y: auto;">
        ${invoicesHtml}
      </div>
    </div>
  `;

  document.getElementById('detailModal').style.display = 'flex';
}

function filterResults(filterType) {
  currentFilter = filterType;

  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.filter === filterType);
  });

  if (lastPipelineResponse) {
    renderResultsTable(lastPipelineResponse.results);
  }
}

function onSearchChange() {
  if (lastPipelineResponse) {
    renderResultsTable(lastPipelineResponse.results);
  }
}

function toggleSort(field) {
  if (currentSortField === field) {
    currentSortOrder = currentSortOrder === 'asc' ? 'desc' : 'asc';
  } else {
    currentSortField = field;
    currentSortOrder = 'asc';
  }
  updateSortIcons();
  if (lastPipelineResponse) {
    renderResultsTable(lastPipelineResponse.results);
  }
}

function updateSortIcons() {
  const fields = ['date', 'gst_total', 'erp_total'];
  fields.forEach(field => {
    const el = document.getElementById(`sort-icon-${field}`);
    if (!el) return;
    if (currentSortField === field) {
      if (currentSortOrder === 'asc') {
        el.innerHTML = `<i class="fa-solid fa-sort-up" style="color: var(--primary);"></i>`;
      } else {
        el.innerHTML = `<i class="fa-solid fa-sort-down" style="color: var(--primary);"></i>`;
      }
    } else {
      el.innerHTML = `<i class="fa-solid fa-sort" style="color: var(--text-dim); opacity: 0.4;"></i>`;
    }
  });
}

function renderResultsTable(results) {
  const tbody = document.getElementById('resultsTableBody');
  tbody.innerHTML = '';

  // 1. Classification Filtering
  let filtered = results.filter(r => {
    if (currentFilter === 'ALL') return true;
    return r.classification === currentFilter;
  });

  // 2. Text Search Filtering
  const searchQuery = (document.getElementById('resultsSearchInput')?.value || '').trim().toLowerCase();
  if (searchQuery) {
    filtered = filtered.filter(r => {
      const gstin = (r.gst_record?.gstin || r.erp_record?.gstin || '').toLowerCase();
      const gstInv = (r.gst_record?.invoice_number || '').toLowerCase();
      const erpInv = (r.erp_record?.invoice_number || '').toLowerCase();
      return gstin.includes(searchQuery) || gstInv.includes(searchQuery) || erpInv.includes(searchQuery);
    });
  }

  // 2.5 Supplier Filtering
  if (activeSupplierFilter) {
    filtered = filtered.filter(r => {
      const gstin = r.gst_record?.gstin || r.erp_record?.gstin || '';
      return gstin === activeSupplierFilter;
    });
  }

  // 3. Sorting
  if (currentSortField === 'date') {
    filtered.sort((a, b) => {
      const dateA = a.gst_record?.invoice_date || a.erp_record?.invoice_date || '';
      const dateB = b.gst_record?.invoice_date || b.erp_record?.invoice_date || '';
      if (dateA === dateB) return 0;
      if (!dateA) return 1;
      if (!dateB) return -1;
      const cmp = dateA < dateB ? -1 : 1;
      return currentSortOrder === 'asc' ? cmp : -cmp;
    });
  } else if (currentSortField === 'gst_total') {
    filtered.sort((a, b) => {
      const valA = a.gst_record?.total_invoice_value ?? 0.0;
      const valB = b.gst_record?.total_invoice_value ?? 0.0;
      const cmp = valA - valB;
      return currentSortOrder === 'asc' ? cmp : -cmp;
    });
  } else if (currentSortField === 'erp_total') {
    filtered.sort((a, b) => {
      const valA = a.erp_record?.total_invoice_value ?? 0.0;
      const valB = b.erp_record?.total_invoice_value ?? 0.0;
      const cmp = valA - valB;
      return currentSortOrder === 'asc' ? cmp : -cmp;
    });
  }

  // 4. Empty State Handler
  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" style="text-align: center; color: var(--text-dim); padding: 36px 24px;">
      <div style="font-size: 24px; color: var(--text-dim); margin-bottom: 8px;"><i class="fa-solid fa-folder-open"></i></div>
      <strong>No Matching Records Found</strong>
      <p style="margin: 4px 0 0 0; font-size: 12px; color: var(--text-muted);">Try adjusting your search query or classification filter.</p>
    </td></tr>`;
    return;
  }

  // 5. Render Rows
  filtered.forEach((res, index) => {
    const tr = document.createElement('tr');

    const gstin = res.gst_record?.gstin || res.erp_record?.gstin || '-';
    const gstInv = res.gst_record?.invoice_number || '-';
    const erpInv = res.erp_record?.invoice_number || '-';
    const dateVal = res.gst_record?.invoice_date || res.erp_record?.invoice_date || '-';
    const gstTotal = res.gst_record ? `₹${res.gst_record.total_invoice_value.toFixed(2)}` : '-';
    const erpTotal = res.erp_record ? `₹${res.erp_record.total_invoice_value.toFixed(2)}` : '-';

    let badgeClass = 'badge-exact';
    if (res.classification === 'PARTIAL_MATCH') badgeClass = 'badge-partial';
    if (res.classification === 'DISCREPANCY') badgeClass = 'badge-discrepancy';
    if (res.classification === 'UNMATCHED') badgeClass = 'badge-unmatched';

    const reviewFlag = res.requires_manual_review ? `<span class="review-flag"><i class="fa-solid fa-triangle-exclamation"></i> Manual Review</span>` : `<span style="color:var(--emerald);"><i class="fa-solid fa-check"></i> Auto Approved</span>`;

    tr.innerHTML = `
      <td><strong>${gstin}</strong></td>
      <td>${gstInv}</td>
      <td>${erpInv}</td>
      <td>${dateVal}</td>
      <td>${gstTotal}</td>
      <td>${erpTotal}</td>
      <td><span class="badge ${badgeClass}">${res.classification}</span></td>
      <td>${reviewFlag}</td>
      <td>
        <button type="button" class="btn secondary-btn" style="padding: 4px 10px; font-size: 12px;" onclick="openDetailModal(${results.indexOf(res)})">
          <i class="fa-solid fa-eye"></i> Detail
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function openDetailModal(index) {
  if (!lastPipelineResponse || !lastPipelineResponse.results[index]) return;

  currentVoucherData = null;
  currentNoticeData = null;

  const res = lastPipelineResponse.results[index];
  const modalBody = document.getElementById('modalBody');

  let diffsHtml = '<p style="color:var(--emerald);"><i class="fa-solid fa-circle-check"></i> No field discrepancies detected across canonical schemas.</p>';
  if (res.field_differences && res.field_differences.length > 0) {
    diffsHtml = `
      <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
        <thead>
          <tr style="border-bottom: 1px solid var(--border-card); text-align: left; color: var(--text-muted);">
            <th style="padding: 6px;">Field</th>
            <th style="padding: 6px;">GST Value</th>
            <th style="padding: 6px;">ERP Value</th>
            <th style="padding: 6px;">Difference</th>
          </tr>
        </thead>
        <tbody>
          ${res.field_differences.map(d => `
            <tr style="border-bottom: 1px solid rgba(0,0,0,0.05);">
              <td style="padding: 6px; font-weight: 600;">${d.field_name}</td>
              <td style="padding: 6px; color: var(--emerald);">${d.gst_value}</td>
              <td style="padding: 6px; color: var(--cyan);">${d.erp_value}</td>
              <td style="padding: 6px; color: var(--rose);">${d.difference_amount !== null ? `₹${d.difference_amount}` : 'Mismatch'}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    `;
  }

  // Find corresponding AI review if present
  let aiReviewHtml = '<p style="color:var(--text-dim);">Exact match — compliance requirement satisfied automatically.</p>';
  if (res.classification === 'EXACT_MATCH') {
    aiReviewHtml = '<p style="color:var(--text-dim);">Exact match — compliance requirement satisfied automatically.</p>';
  } else {
    let aiReview = null;
    if (lastPipelineResponse.ai_reviews) {
      const nonExactResults = lastPipelineResponse.results.filter(r => r.classification !== 'EXACT_MATCH');
      const nonExactIdx = nonExactResults.indexOf(res);
      if (nonExactIdx !== -1 && lastPipelineResponse.ai_reviews[nonExactIdx]) {
        aiReview = lastPipelineResponse.ai_reviews[nonExactIdx];
      }
    }

    if (aiReview) {
      aiReviewHtml = `
        <p style="margin-bottom: 6px;"><strong>Explanation:</strong> ${aiReview.explanation}</p>
        <p style="margin-bottom: 6px;"><strong>AI Remark:</strong> ${aiReview.ai_remark}</p>
        <p style="margin-bottom: 6px;"><strong>Audit Note:</strong> ${aiReview.audit_remark}</p>
        <p style="color: var(--cyan); font-weight: 600;"><strong>Recommended Action:</strong> ${aiReview.recommended_action}</p>
      `;
    } else if (res.classification === 'DISCREPANCY' || res.classification === 'PARTIAL_MATCH') {
      aiReviewHtml = `
        <div id="aiDiscrepancyExplanationContainer">
          <button type="button" class="btn primary-btn" style="width: 100%; display: flex; justify-content: center; align-items: center; gap: 8px;" onclick="generateSingleAIDiscrepancyReview(${index})">
            <i class="fa-solid fa-wand-magic-sparkles"></i> Generate AI Discrepancy Explanation
          </button>
        </div>
      `;
    } else {
      aiReviewHtml = '<p style="color:var(--text-dim);">Record is unmatched. Compliance actions require primary mapping review.</p>';
    }
  }

  const supplierGstin = res.gst_record?.gstin || res.erp_record?.gstin || '';
  
  // Render M12 Resolution Generator placeholder for non-exact matches
  let resolutionContainerHtml = '';
  if (res.classification !== 'EXACT_MATCH') {
    resolutionContainerHtml = `
      <div class="modal-section" style="margin-top: 16px;">
        <h4 style="font-size: 14px; color: var(--text-dim); margin-bottom: 8px;"><i class="fa-solid fa-calculator"></i> AI Accounting Resolution Voucher</h4>
        <div id="aiResolutionVoucherContainer">
          <button type="button" class="btn primary-btn" style="width: 100%; display: flex; justify-content: center; align-items: center; gap: 8px;" id="generateResolutionBtn" onclick="generateAIResolution(${index}, '${supplierGstin}')">
            <i class="fa-solid fa-wand-magic-sparkles"></i> Generate AI Accounting Resolution & Vendor Notice
          </button>
        </div>
      </div>
    `;
  }

  modalBody.innerHTML = `
    <div class="modal-section" style="margin-bottom: 16px;">
      <h4 style="font-size: 14px; color: var(--text-dim); margin-bottom: 6px;">Classification & Status</h4>
      <span class="badge ${res.classification === 'EXACT_MATCH' ? 'badge-exact' : (res.classification === 'PARTIAL_MATCH' ? 'badge-partial' : (res.classification === 'DISCREPANCY' ? 'badge-discrepancy' : 'badge-unmatched'))}">${res.classification}</span>
      ${res.unmatched_reason ? `<span class="badge badge-unmatched" style="margin-left: 8px;">${res.unmatched_reason}</span>` : ''}
      ${res.requires_manual_review ? `<span class="review-flag" style="margin-left: 8px;"><i class="fa-solid fa-triangle-exclamation"></i> Manual Review Required</span>` : ''}
    </div>

    <div class="modal-section" style="margin-bottom: 16px;">
      <h4 style="font-size: 14px; color: var(--text-muted); margin-bottom: 6px;">Field Comparison Matrix</h4>
      <div class="modal-box" style="background: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid var(--border-card);">${diffsHtml}</div>
    </div>

    <div class="modal-section" style="margin-bottom: 16px;">
      <h4 style="font-size: 14px; color: var(--text-muted); margin-bottom: 6px;">AI Audit Insights</h4>
      <div class="modal-box" style="background: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid var(--border-card);">${aiReviewHtml}</div>
    </div>

    ${resolutionContainerHtml}
  `;

  document.getElementById('detailModal').style.display = 'flex';
}

async function generateAIResolution(index, supplierGstin) {
  if (!lastPipelineResponse || !lastPipelineResponse.results[index]) return;

  const res = lastPipelineResponse.results[index];
  const btn = document.getElementById('generateResolutionBtn');
  const container = document.getElementById('aiResolutionVoucherContainer');

  if (btn) {
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Analyzing compliance rules...`;
    btn.disabled = true;
  }

  try {
    const response = await fetch('/api/v1/ai/generate-resolution', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        reconciliation_result: res,
        supplier_name: supplierGstin || "Vendor"
      })
    });

    if (!response.ok) {
      container.innerHTML = `<p style="color:var(--rose); font-size: 13px;"><i class="fa-solid fa-circle-exclamation"></i> Resolution recommendation failed to generate.</p>`;
      return;
    }

    const data = await response.json();
    currentVoucherData = data.adjustment_voucher;
    currentNoticeData = data.vendor_notice;
    renderAIResolutionVoucher(container, data);
  } catch (err) {
    container.innerHTML = `<p style="color:var(--rose); font-size: 13px;"><i class="fa-solid fa-circle-exclamation"></i> Network error: ${err.message}</p>`;
  }
}

function renderAIResolutionVoucher(container, data) {
  let voucherHtml = '<p style="color:var(--text-dim); font-size:13px; font-style:italic;">No adjustments required in ERP ledgers.</p>';
  if (data.adjustment_voucher) {
    const v = data.adjustment_voucher;
    voucherHtml = `
      <div class="ai-voucher-card">
        <div class="ai-voucher-header">
          <div class="ai-voucher-title">
            <i class="fa-solid fa-money-bill-transfer"></i> ERP Adjustment Entry
          </div>
          <span class="badge badge-partial" style="text-transform: uppercase;">${v.voucher_type}</span>
        </div>
        <div class="ai-voucher-grid">
          <span class="ai-voucher-label">Debit Account:</span>
          <span class="ai-voucher-val" style="color: var(--rose);">${v.debit_account}</span>
          
          <span class="ai-voucher-label">Credit Account:</span>
          <span class="ai-voucher-val" style="color: var(--emerald);">${v.credit_account}</span>
          
          <span class="ai-voucher-label">Voucher Amount:</span>
          <span class="ai-voucher-val" style="font-weight: 700; color: var(--cyan);">₹${v.amount.toFixed(2)}</span>
        </div>
        
        <div class="ai-voucher-label" style="margin-bottom: 6px; display: block;">Voucher Narration:</div>
        <div class="ai-voucher-narration" id="narrationText">${v.narration}</div>
        
        <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px;">
          <button type="button" class="copy-btn" id="copyNarrationBtn" onclick="copyTextToClipboard('narrationText', 'copyNarrationBtn')">
            <i class="fa-solid fa-copy"></i> Copy Narration
          </button>
          <button type="button" class="copy-btn" id="exportVoucherTxtBtn" onclick="exportVoucher('txt', 'exportVoucherTxtBtn')">
            <i class="fa-solid fa-file-lines"></i> Export TXT
          </button>
          <button type="button" class="copy-btn" id="exportVoucherJsonBtn" onclick="exportVoucher('json', 'exportVoucherJsonBtn')">
            <i class="fa-solid fa-file-code"></i> Export JSON
          </button>
        </div>
      </div>
    `;
  }

  let noticeHtml = '';
  if (data.vendor_notice) {
    const n = data.vendor_notice;
    noticeHtml = `
      <div class="vendor-notice-card">
        <div style="display:flex; justify-content:space-between; align-items:center; border-bottom: 1px solid rgba(0, 0, 0, 0.08); padding-bottom:6px; margin-bottom:8px;">
          <div style="font-weight: 700; color: var(--amber); font-size:13px; text-transform:uppercase;">
            <i class="fa-solid fa-envelope-open-text"></i> Supplier Notice Draft
          </div>
        </div>
        <div style="font-size:12.5px; color: var(--text-main); margin-bottom:4px;"><strong>Subject:</strong> ${n.subject}</div>
        <div style="font-size:12.5px; color: var(--text-dim);"><strong>To:</strong> ${n.recipient_name} (${n.recipient_gstin})</div>
        <div class="vendor-notice-body" id="vendorNoticeText">${n.notice_body}</div>
        
        <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px;">
          <button type="button" class="copy-btn" id="copyNoticeBtn" onclick="copyTextToClipboard('vendorNoticeText', 'copyNoticeBtn')">
            <i class="fa-solid fa-copy"></i> Copy Notice
          </button>
          <button type="button" class="copy-btn" id="exportNoticeTxtBtn" onclick="exportNotice('txt', 'exportNoticeTxtBtn')">
            <i class="fa-solid fa-file-lines"></i> Export TXT
          </button>
          <button type="button" class="copy-btn" id="exportNoticeJsonBtn" onclick="exportNotice('json', 'exportNoticeJsonBtn')">
            <i class="fa-solid fa-file-code"></i> Export JSON
          </button>
        </div>
      </div>
    `;
  }

  container.innerHTML = `
    <div style="background: rgba(99, 102, 241, 0.05); padding: 12px; border-radius: var(--radius-sm); border: 1px solid rgba(99, 102, 241, 0.2); margin-bottom: 12px; font-size: 13px;">
      <div style="font-weight: 700; color: var(--text-main); margin-bottom: 4px;">Recommended Action:</div>
      <div style="color: var(--cyan); font-weight: 600; text-transform: uppercase; font-size: 12px; margin-bottom: 8px;">
        <i class="fa-solid fa-circle-info"></i> ${data.action_type}
      </div>
      <p style="color: var(--text-muted); line-height: 1.4;">${data.reasoning}</p>
    </div>
    ${voucherHtml}
    ${noticeHtml}
  `;
}

function copyTextToClipboard(elementId, btnId) {
  const text = document.getElementById(elementId).innerText;
  const btn = document.getElementById(btnId);
  const originalHtml = btn.innerHTML;

  navigator.clipboard.writeText(text).then(() => {
    btn.innerHTML = `<i class="fa-solid fa-check"></i> Copied!`;
    btn.style.background = 'var(--emerald)';
    btn.style.color = '#ffffff';
    setTimeout(() => {
      btn.innerHTML = originalHtml;
      btn.style.background = '';
      btn.style.color = '';
    }, 2000);
  }).catch(err => {
    console.error('Clipboard copy failed:', err);
  });
}

function exportVoucher(format, btnId) {
  if (!currentVoucherData) return;

  let content = '';
  let filename = 'erp_adjustment_voucher';
  let mimeType = 'text/plain';

  if (format === 'json') {
    content = JSON.stringify(currentVoucherData, null, 2);
    filename += '.json';
    mimeType = 'application/json';
  } else {
    content = `--- ERP ADJUSTMENT VOUCHER ---
Voucher Type: ${currentVoucherData.voucher_type}
Debit Account: ${currentVoucherData.debit_account}
Credit Account: ${currentVoucherData.credit_account}
Voucher Amount: INR ${currentVoucherData.amount.toFixed(2)}
Voucher Narration:
${currentVoucherData.narration}
`;
    filename += '.txt';
  }

  downloadBlob(content, filename, mimeType);
  showSuccessFeedback(btnId, 'Exported!');
}

function exportNotice(format, btnId) {
  if (!currentNoticeData) return;

  let content = '';
  let filename = 'supplier_reconciliation_notice';
  let mimeType = 'text/plain';

  if (format === 'json') {
    content = JSON.stringify(currentNoticeData, null, 2);
    filename += '.json';
    mimeType = 'application/json';
  } else {
    content = `Subject: ${currentNoticeData.subject}
Recipient Name: ${currentNoticeData.recipient_name}
Recipient GSTIN: ${currentNoticeData.recipient_gstin}

Dear Supplier,

${currentNoticeData.notice_body}
`;
    filename += '.txt';
  }

  downloadBlob(content, filename, mimeType);
  showSuccessFeedback(btnId, 'Exported!');
}

function downloadBlob(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function showSuccessFeedback(btnId, feedbackText) {
  const btn = document.getElementById(btnId);
  if (!btn) return;
  const originalHtml = btn.innerHTML;
  btn.innerHTML = `<i class="fa-solid fa-check"></i> ${feedbackText}`;
  btn.style.background = 'var(--emerald)';
  btn.style.color = '#ffffff';
  setTimeout(() => {
    btn.innerHTML = originalHtml;
    btn.style.background = '';
    btn.style.color = '';
  }, 2000);
}

function closeModal() {
  document.getElementById('detailModal').style.display = 'none';
}


async function fetchAuditTrail() {
  const modalBody = document.getElementById('modalBody');
  if (!modalBody) return;

  // Show a proper loading spinner state first
  modalBody.innerHTML = `
    <div style="text-align: center; padding: 40px 24px; color: var(--text-dim);">
      <div style="font-size: 32px; margin-bottom: 12px;"><i class="fa-solid fa-spinner fa-spin" style="color: var(--primary);"></i></div>
      <strong>Loading Audit History...</strong>
    </div>
  `;
  document.getElementById('detailModal').style.display = 'flex';

  try {
    const response = await fetch('/api/v1/orchestration/audit-trail');
    if (!response.ok) {
      modalBody.innerHTML = `<p style="text-align: center; color: var(--rose); padding: 24px;">Failed to retrieve audit trail.</p>`;
      return;
    }
    const history = await response.json();
    currentAuditTrailList = history;

    if (history.length === 0) {
      modalBody.innerHTML = `
        <div style="text-align: center; color: var(--text-dim); padding: 40px 24px;">
          <div style="font-size: 32px; color: var(--text-muted); margin-bottom: 12px;"><i class="fa-solid fa-clock-rotate-left"></i></div>
          <strong>No Audit History Found</strong>
          <p style="margin: 6px 0 0 0; font-size: 12px; color: var(--text-muted);">Perform a reconciliation run to record your first audit log entry.</p>
        </div>
      `;
    } else {
      modalBody.innerHTML = `
        <h4 style="font-size: 14px; color: var(--text-dim); margin-bottom: 12px;">Recent Reconciliation Audit Runs</h4>
        <div style="max-height: 400px; overflow-y: auto; padding-right: 4px;">
          ${history.map((item, idx) => {
            const hasData = !!item.full_pipeline_response;
            const actionHtml = hasData 
              ? `<button type="button" class="btn primary-btn" style="padding: 4px 10px; font-size: 11.5px; margin-top: 10px; display: inline-flex; align-items: center; gap: 6px;" onclick="loadHistoricalRun(${idx})"><i class="fa-solid fa-folder-open"></i> Load Run Data</button>` 
              : `<span style="font-size: 11.5px; color: var(--text-dim); display: block; margin-top: 10px; font-style: italic;"><i class="fa-solid fa-circle-info"></i> No saved detail results</span>`;
              
            return `
              <div style="padding: 12px; margin-bottom: 10px; background: #f8fafc; border: 1px solid var(--border-card); border-radius: 8px;">
                <div style="display: flex; justify-content: space-between; font-size: 11px; color: var(--text-dim); margin-bottom: 6px;">
                  <span><i class="fa-solid fa-clock"></i> ${new Date(item.timestamp).toLocaleString()}</span>
                  <span>ID: ${item.audit_id.substring(0, 8)}...</span>
                </div>
                <div style="font-size: 13px; font-weight: 600; margin-bottom: 4px; color: var(--text-main);">
                  ${item.gst_filename} vs ${item.erp_filename}
                </div>
                <div style="font-size: 12px; color: var(--text-muted); line-height: 1.4;">
                  GST Invoices: ${item.total_gst_records} | ERP Invoices: ${item.total_erp_records}<br>
                  Eligible ITC: <strong>₹${item.itc_claimable_amount.toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong> | Disputed: <strong>₹${item.itc_disputed_amount.toLocaleString('en-IN', {minimumFractionDigits: 2})}</strong>
                </div>
                ${actionHtml}
              </div>
            `;
          }).join('')}
        </div>
      `;
    }
  } catch (err) {
    modalBody.innerHTML = `<p style="text-align: center; color: var(--rose); padding: 24px;">Error: ${err.message}</p>`;
  }
}

function startNewReconciliation() {
  selectedGstFile = null;
  selectedErpFile = null;
  lastGstHeaders = null;
  lastErpHeaders = null;
  lastPairwiseRole = null;
  lastPipelineResponse = null;
  currentFilter = 'ALL';
  currentSortField = null;
  currentSortOrder = 'asc';
  currentVoucherData = null;
  currentNoticeData = null;
  activeSupplierFilter = null;
  lastRiskReport = null;
  currentSupplierSortField = null;
  currentSupplierSortOrder = 'asc';

  const supplierBadge = document.getElementById('activeSupplierFilterBadge');
  if (supplierBadge) supplierBadge.style.display = 'none';

  const sameFileWarn = document.getElementById('sameFileValidationError');
  if (sameFileWarn) sameFileWarn.style.display = 'none';

  const roleWarn = document.getElementById('fileRoleValidationError');
  if (roleWarn) roleWarn.style.display = 'none';

  const suppSearch = document.getElementById('supplierSearchInput');
  if (suppSearch) suppSearch.value = '';

  const suppFilter = document.getElementById('supplierRiskFilter');
  if (suppFilter) suppFilter.value = 'ALL';

  // Reset file inputs
  document.getElementById('gstFileInput').value = '';
  document.getElementById('erpFileInput').value = '';

  // Reset UI file boxes
  document.getElementById('gstFileName').innerText = '';
  document.getElementById('gstFileInfo').style.display = 'none';
  document.getElementById('erpFileName').innerText = '';
  document.getElementById('erpFileInfo').style.display = 'none';

  // Hide panels
  document.getElementById('mappingPanel').style.display = 'none';
  document.getElementById('configBar').style.display = 'none';
  document.getElementById('dashboardPanel').style.display = 'none';
  document.getElementById('resultsPanel').style.display = 'none';
  const vendorRiskContainer = document.getElementById('vendorRiskContainer');
  if (vendorRiskContainer) vendorRiskContainer.style.display = 'none';

  // Hide the "Start New Reconciliation" button itself
  const resetBtn = document.getElementById('startNewReconcileBtn');
  if (resetBtn) resetBtn.style.display = 'none';

  // Clear tables and selections
  document.getElementById('gstMappingTableBody').innerHTML = '';
  document.getElementById('erpMappingTableBody').innerHTML = '';
  document.getElementById('resultsTableBody').innerHTML = '';
  
  const searchInput = document.getElementById('resultsSearchInput');
  if (searchInput) searchInput.value = '';

  // Reset tab active states
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.filter === 'ALL');
  });

  // Scroll back to top
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function loadHistoricalRun(idx) {
  if (!currentAuditTrailList || !currentAuditTrailList[idx]) return;
  const run = currentAuditTrailList[idx];
  if (!run.full_pipeline_response) {
    alert('This historical entry has no saved detailed results.');
    return;
  }
  
  // Load state
  lastPipelineResponse = run.full_pipeline_response;
  
  // Render Dashboard & Results table
  renderDashboard(lastPipelineResponse);
  renderResultsTable(lastPipelineResponse.results);
  
  // Set file upload panel states to reflect files
  document.getElementById('gstFileName').innerText = run.gst_filename;
  document.getElementById('gstFileInfo').style.display = 'inline-flex';
  document.getElementById('erpFileName').innerText = run.erp_filename;
  document.getElementById('erpFileInfo').style.display = 'inline-flex';
  
  // Show sections
  document.getElementById('dashboardPanel').style.display = 'block';
  document.getElementById('resultsPanel').style.display = 'block';
  
  // Hide column mapping panels since we are displaying historical results
  document.getElementById('mappingPanel').style.display = 'none';
  document.getElementById('configBar').style.display = 'none';
  
  // Show the "Start New Reconciliation" button in header
  const resetBtn = document.getElementById('startNewReconcileBtn');
  if (resetBtn) resetBtn.style.display = 'inline-flex';
  
  // Close modal
  closeModal();
  
  // Scroll to dashboard
  document.getElementById('dashboardPanel').scrollIntoView({ behavior: 'smooth' });
}


async function exportCsvReport() {
  if (!lastPipelineResponse) return;

  const batchPayload = {
    summary: lastPipelineResponse.batch_summary,
    results: lastPipelineResponse.results,
  };

  try {
    const response = await fetch('/api/v1/orchestration/export-csv', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(batchPayload),
    });

    if (!response.ok) {
      alert('CSV export failed.');
      return;
    }

    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'gst_reconciliation_audit_report.csv';
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (err) {
    alert(`CSV export error: ${err.message}`);
  }
}

async function generateSingleAIDiscrepancyReview(index) {
  if (!lastPipelineResponse || !lastPipelineResponse.results[index]) return;

  const res = lastPipelineResponse.results[index];
  const container = document.getElementById('aiDiscrepancyExplanationContainer');
  if (!container) return;

  container.innerHTML = `<div style="text-align: center; color: var(--text-dim); padding: 12px;"><i class="fa-solid fa-spinner fa-spin"></i> Analyzing discrepancies...</div>`;

  try {
    const response = await fetch('/api/v1/ai/review-discrepancy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reconciliation_result: res })
    });

    if (!response.ok) {
      throw new Error('API failure');
    }

    const aiReview = await response.json();
    
    // Save to lastPipelineResponse.ai_reviews list to keep it cache-consistent
    if (!lastPipelineResponse.ai_reviews) {
      lastPipelineResponse.ai_reviews = [];
    }
    const nonExactResults = lastPipelineResponse.results.filter(r => r.classification !== 'EXACT_MATCH');
    const nonExactIdx = nonExactResults.indexOf(res);
    if (nonExactIdx !== -1) {
      lastPipelineResponse.ai_reviews[nonExactIdx] = aiReview;
    }

    renderSingleAIDiscrepancyReview(container, aiReview);

  } catch (err) {
    // Deterministic fallback response if gateway fails
    const fallbackReview = getDeterministicFallbackReview(res);
    renderSingleAIDiscrepancyReview(container, fallbackReview);
  }
}

function getDeterministicFallbackReview(res) {
  let explanation = '';
  if (res.classification === 'PARTIAL_MATCH') {
    explanation = 'The invoice exists in both GSTR-2B and ERP, but there are minor discrepancies in fields (like dates or amounts) within standard tolerance limits.';
  } else if (res.classification === 'DISCREPANCY') {
    explanation = 'Significant discrepancies detected. Field values differ beyond acceptable tolerances, indicating potential tax liability mismatch or supplier filing error.';
  } else {
    explanation = 'Record is unmatched in either the GST dataset or ERP purchase register.';
  }

  return {
    explanation: explanation,
    ai_remark: `${res.classification}: Field evaluation completed.`,
    audit_remark: 'Manual review recommended prior to ITC claim filing.',
    recommended_action: 'Inspect field differences and vendor invoice document.'
  };
}

function renderSingleAIDiscrepancyReview(container, aiReview) {
  container.innerHTML = `
    <p style="margin-bottom: 6px;"><strong>Explanation:</strong> ${aiReview.explanation}</p>
    <p style="margin-bottom: 6px;"><strong>AI Remark:</strong> ${aiReview.ai_remark}</p>
    <p style="margin-bottom: 6px;"><strong>Audit Note:</strong> ${aiReview.audit_remark}</p>
    <p style="color: var(--cyan); font-weight: 600;"><strong>Recommended Action:</strong> ${aiReview.recommended_action}</p>
  `;
}

// --- Mock Data ---
const MOCK_DATA = {
    "documents": [
        {
            "doc_type": "invoice_sf",
            "raw_text": "...",
            "structured": {
                "document_title": { "value": "Счет-фактура", "confidence": 0.99 },
                "document_number": { "value": "12345", "confidence": 0.98 },
                "document_date": { "value": "12.02.2025", "confidence": 0.98 },
                "currency": { "value": "RUB", "confidence": 0.95 },

                "seller": {
                    "name": { "value": "ООО 'Ромашка'", "confidence": 0.99 },
                    "inn": { "value": "7700000000", "confidence": 0.99 },
                    "kpp": { "value": "770101001", "confidence": 0.99 },
                    "address": { "value": "г. Москва, ул. Ленина, д. 1", "confidence": 0.95 }
                },

                "buyer": {
                    "name": { "value": "ПАО 'Газпром'", "confidence": 0.99 },
                    "inn": { "value": "9900000000", "confidence": 0.99 },
                    "kpp": { "value": "990101001", "confidence": 0.99 },
                    "address": { "value": "г. Санкт-Петербург, Лахта Центр", "confidence": 0.95 }
                },

                "amounts": {
                    "subtotal_without_vat": { "value": 100000.00, "confidence": 0.99 },
                    "vat_amount": { "value": 20000.00, "confidence": 0.99 },
                    "total_with_vat": { "value": 120000.00, "confidence": 0.99 }
                },

                "items": [
                    {
                        "line_number": { "value": 1, "confidence": 1 },
                        "name": { "value": "Услуги по разработке ПО", "confidence": 0.98 },
                        "unit": { "value": "ч", "confidence": 0.9 },
                        "quantity": { "value": 100, "confidence": 0.95 },
                        "price_without_vat": { "value": 1000.00, "confidence": 0.98 },
                        "amount_without_vat": { "value": 100000.00, "confidence": 0.98 },
                        "vat_rate": { "value": "20%", "confidence": 0.99 },
                        "vat_amount": { "value": 20000.00, "confidence": 0.98 },
                        "amount_with_vat": { "value": 120000.00, "confidence": 0.98 }
                    }
                ]
            },
            "visual_marks": {
                "seals": [
                    {
                        "page": 1,
                        "bbox": { "x1": 100, "y1": 100, "x2": 200, "y2": 200 },
                        "type": "circle",
                        "text": { "value": "ООО Ромашка", "confidence": 0.9 },
                        "confidence": 0.95
                    }
                ],
                "signatures": [
                    {
                        "page": 1,
                        "bbox": { "x1": 300, "y1": 400, "x2": 400, "y2": 450 },
                        "role": "director",
                        "name": { "value": "Иванов И.И.", "confidence": 0.9 },
                        "confidence": 0.9
                    }
                ]
            }
        }
    ]
};

// --- Create Lucide Icons ---
lucide.createIcons();

// --- Constants ---
const API_URL = 'https://ces-n8n-01.askonalife.com/webhook/ocr-idp';

// --- DOM Elements ---
const ui = {
    uploadArea: document.getElementById('upload-area'),
    dashboard: document.getElementById('dashboard'),
    fileInput: document.getElementById('file-input'),
    loader: document.getElementById('loader'),
    resultsContainer: document.getElementById('results-container'),
    docTypeBadge: document.getElementById('doc-type-badge'),
    pdfCanvas: document.getElementById('pdf-canvas'),
    btnReset: document.getElementById('btn-reset'),
    btnShowRaw: document.getElementById('btn-show-raw'),
    btnShowJson: document.getElementById('btn-show-json'),
    modalRaw: document.getElementById('modal-raw'),
    modalJson: document.getElementById('modal-json'),
    rawTextContent: document.getElementById('raw-text-content'),
    jsonContent: document.getElementById('json-content'),
    closeModals: document.querySelectorAll('.close-modal'),
    // Navigation
    docNavigation: document.getElementById('doc-navigation'),
    btnPrevDoc: document.getElementById('btn-prev-doc'),
    btnNextDoc: document.getElementById('btn-next-doc'),
    docCounter: document.getElementById('doc-counter')
};

// --- State ---
let currentFile = null;
let currentData = null;
let currentDocIndex = 0;

// --- Event Listeners ---
ui.fileInput.addEventListener('change', handleFileSelect);
ui.btnReset.addEventListener('click', resetApp);

// Navigation
ui.btnPrevDoc.addEventListener('click', () => changeDoc(-1));
ui.btnNextDoc.addEventListener('click', () => changeDoc(1));

// Drag & Drop
ui.uploadArea.addEventListener('dragover', (e) => { e.preventDefault(); ui.uploadArea.style.borderColor = 'var(--primary)'; });
ui.uploadArea.addEventListener('dragleave', (e) => { e.preventDefault(); ui.uploadArea.style.borderColor = 'var(--border)'; });
ui.uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    ui.uploadArea.style.borderColor = 'var(--border)';
    if (e.dataTransfer.files.length) {
        handleFile(e.dataTransfer.files[0]);
    }
});

// Modals
ui.btnShowRaw.addEventListener('click', () => showModal('raw'));
ui.btnShowJson.addEventListener('click', () => showModal('json'));
ui.closeModals.forEach(btn => btn.addEventListener('click', () => {
    ui.modalRaw.classList.add('hidden');
    ui.modalJson.classList.add('hidden');
}));

// --- Functions ---

function handleFileSelect(e) {
    if (e.target.files.length) {
        handleFile(e.target.files[0]);
    }
}

function handleFile(file) {
    if (file.type !== 'application/pdf') {
        alert('Пожалуйста, загрузите PDF файл');
        return;
    }
    currentFile = file;

    // Switch view to dashboard immediately so canvas has dimensions
    ui.uploadArea.classList.add('hidden');
    ui.dashboard.classList.remove('hidden');

    renderPdfPreview(file);
    uploadAndProcess(file);
}

async function renderPdfPreview(file) {
    const fileReader = new FileReader();
    fileReader.onload = function () {
        const typedarray = new Uint8Array(this.result);

        pdfjsLib.getDocument(typedarray).promise.then(function (pdf) {
            // Fetch the first page
            pdf.getPage(1).then(function (page) {
                const canvas = ui.pdfCanvas;
                const context = canvas.getContext('2d');

                // Calculate scale to fit width
                const containerWidth = document.getElementById('pdf-render-container').clientWidth - 40;
                const viewport = page.getViewport({ scale: 1 });
                const scale = containerWidth / viewport.width;
                const scaledViewport = page.getViewport({ scale: scale });

                canvas.height = scaledViewport.height;
                canvas.width = scaledViewport.width;

                const renderContext = {
                    canvasContext: context,
                    viewport: scaledViewport
                };
                page.render(renderContext);
            });
        });
    };
    fileReader.readAsArrayBuffer(file);
}

async function uploadAndProcess(file) {
    setLoading(true);

    // Simulate FormData
    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(API_URL, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error(`HTTP Error: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();
        console.log('API Response:', data); // Debug log
        currentData = data;
        renderApp(data);

    } catch (error) {
        console.error(error);
        alert(`Ошибка при обработке файла: ${error.message}. Проверьте консоль (F12) для деталей.`);
        resetApp();
    } finally {
        setLoading(false);
    }
}

function renderApp(data) {
    // Try to find documents array in different common places
    let docs = data.documents;
    if (!docs && data.output && data.output.documents) {
        docs = data.output.documents;
    }

    if (!docs || !Array.isArray(docs) || !docs.length) {
        console.error('Invalid Data Structure:', data);
        alert('Некорректный формат ответа от сервера. Проверьте консоль, чтобы увидеть полученный JSON.');
        return;
    }

    // Initialize Navigation
    currentDocIndex = 0;

    // Reset View & Ensure Visibility
    ui.resultsContainer.innerHTML = '';
    ui.uploadArea.classList.add('hidden');
    ui.dashboard.classList.remove('hidden');

    updateDocView();
}

function changeDoc(delta) {
    if (!currentData) return;

    let docs = currentData.documents || currentData.output?.documents;
    if (!docs) return;

    let newIndex = currentDocIndex + delta;
    if (newIndex >= 0 && newIndex < docs.length) {
        currentDocIndex = newIndex;
        updateDocView();
    }
}

function updateDocView() {
    let docs = currentData.documents || currentData.output?.documents;
    const doc = docs[currentDocIndex];
    const structured = doc.structured;

    // Update Navigation UI
    if (docs.length > 1) {
        ui.docNavigation.classList.remove('hidden');
        ui.docCounter.textContent = `${currentDocIndex + 1} / ${docs.length}`;
        ui.btnPrevDoc.disabled = currentDocIndex === 0;
        ui.btnNextDoc.disabled = currentDocIndex === docs.length - 1;
        // Visual opacity for disabled state can be handled by CSS or standard behavior
        ui.btnPrevDoc.style.opacity = currentDocIndex === 0 ? '0.5' : '1';
        ui.btnNextDoc.style.opacity = currentDocIndex === docs.length - 1 ? '0.5' : '1';
    } else {
        ui.docNavigation.classList.add('hidden');
    }

    // Clear Container for re-render
    ui.resultsContainer.innerHTML = '';

    // 1. Meta & Badge
    ui.docTypeBadge.textContent = mapDocType(doc.doc_type);

    // 2. Render Blocks

    // --- Header Info (Number, Date, etc.) ---
    const headerFields = [
        { label: 'Номер документа', value: structured.document_number?.value },
        { label: 'Дата документа', value: structured.document_date?.value },
        { label: 'Название', value: structured.document_title?.value },
        { label: 'Валюта', value: structured.currency?.value },
    ];
    // Basis document logic
    if (structured.basis_document) {
        headerFields.push({ label: 'Основание (Тип)', value: structured.basis_document.type?.value });
        headerFields.push({ label: 'Основание (Номер)', value: structured.basis_document.number?.value });
        headerFields.push({ label: 'Основание (Дата)', value: structured.basis_document.date?.value });
    }

    renderCard('Основная информация', headerFields, 'file-text');

    // --- Seller & Buyer ---
    if (structured.seller) {
        renderCard('Продавец', formatParty(structured.seller), 'building', 'seller-card');
    }
    if (structured.buyer) {
        renderCard('Покупатель', formatParty(structured.buyer), 'building-2', 'buyer-card');
    }

    // --- Consignor / Consignee (Optional) ---
    if (structured.consignor && hasValue(structured.consignor)) {
        renderCard('Грузоотправитель', formatParty(structured.consignor), 'truck');
    }
    if (structured.consignee && hasValue(structured.consignee)) {
        renderCard('Грузополучатель', formatParty(structured.consignee), 'package');
    }

    // --- Items ---
    if (structured.items && structured.items.length) {
        renderItems(structured.items);
    }

    // --- Amounts ---
    if (structured.amounts) {
        renderAmounts(structured.amounts);
    }

    // --- Visual Marks ---
    if (doc.visual_marks && (doc.visual_marks.seals?.length || doc.visual_marks.signatures?.length)) {
        renderVisualMarks(doc.visual_marks);
    }

    // --- Data for Modals ---
    ui.rawTextContent.textContent = doc.raw_text || 'Нет текста';
    ui.jsonContent.textContent = JSON.stringify(currentData, null, 2);

    // Re-init icons
    lucide.createIcons();
}

// --- Helpers ---

function hasValue(obj) {
    if (!obj) return false;
    // Check if any property in the object has a non-null value
    return Object.values(obj).some(prop => prop && prop.value);
}

function formatParty(partyObj) {
    if (!partyObj) return [];
    return [
        { label: 'Название', value: partyObj.name?.value },
        { label: 'ИНН', value: partyObj.inn?.value },
        { label: 'КПП', value: partyObj.kpp?.value },
        { label: 'Адрес', value: partyObj.address?.value },
    ];
}

function renderCard(title, fields, icon, className = '') {
    // Filter out nulls
    const validFields = fields.filter(f => f.value != null);
    if (!validFields.length) return;

    const card = document.createElement('div');
    card.className = `card ${className}`;

    let fieldsHtml = validFields.map(f => `
      <div class="field">
        <div class="field-label">${f.label}</div>
        <div class="field-value">${f.value}</div>
      </div>
    `).join('');

    card.innerHTML = `
      <div class="card-title">
        <i data-lucide="${icon}"></i> ${title}
      </div>
      <div class="info-grid">
        ${fieldsHtml}
      </div>
    `;
    ui.resultsContainer.appendChild(card);
}

function renderItems(items) {
    const card = document.createElement('div');
    card.className = 'card';

    // Helper to safe get value
    const v = (item, key) => item[key]?.value ?? '-';
    // Helper to format money
    const m = (val) => typeof val === 'number' ? formatCurrency(val) : val;

    const rows = items.map((item) => `
      <tr>
        <td>${v(item, 'line_number')}</td>
        <td>${v(item, 'name')} <br/> <small style="color:#94a3b8">${v(item, 'code_okpd2') !== '-' ? 'Код: ' + v(item, 'code_okpd2') : ''}</small></td>
        <td class="text-center">${v(item, 'unit')}</td>
        <td class="text-center">${v(item, 'quantity')}</td>
        <td class="text-right">${m(item.price_without_vat?.value)}</td>
        <td class="text-right">${v(item, 'vat_rate')}</td>
        <td class="text-right">${m(item.amount_with_vat?.value)}</td>
      </tr>
    `).join('');

    card.innerHTML = `
      <div class="card-title">
        <i data-lucide="list"></i> Позиции документа
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Наименование</th>
              <th class="text-center">Ед.</th>
              <th class="text-center">Кол-во</th>
              <th class="text-right">Цена</th>
              <th class="text-right">НДС</th>
              <th class="text-right">Всего</th>
            </tr>
          </thead>
          <tbody>
            ${rows}
          </tbody>
        </table>
      </div>
    `;
    ui.resultsContainer.appendChild(card);
}

function renderAmounts(amounts) {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `
      <div class="card-title">
        <i data-lucide="calculator"></i> Итоговые суммы
      </div>
      <div class="amounts-grid">
        <div class="amount-item">
          <div class="field-label">Сумма без НДС</div>
          <div class="field-value">${formatCurrency(amounts.subtotal_without_vat?.value)}</div>
        </div>
        <div class="amount-item">
          <div class="field-label">НДС</div>
          <div class="field-value">${formatCurrency(amounts.vat_amount?.value)}</div>
        </div>
        <div class="amount-item total">
          <div class="field-label">Итого к оплате</div>
          <div class="field-value">${formatCurrency(amounts.total_with_vat?.value)}</div>
        </div>
      </div>
    `;
    ui.resultsContainer.appendChild(card);
}

function renderVisualMarks(marks) {
    const card = document.createElement('div');
    card.className = 'card';

    let html = `<div class="card-title"><i data-lucide="stamp"></i> Печати и подписи</div><div class="marks-list">`;

    if (marks.seals) {
        marks.seals.forEach(seal => {
            if (seal.text?.value) {
                html += `<div class="mark-tag"><i data-lucide="stamp" size="14"></i> Печать: ${seal.text.value}</div>`;
            }
        });
    }
    if (marks.signatures) {
        marks.signatures.forEach(sig => {
            let label = sig.role || 'Подпись';
            if (sig.name?.value) {
                label += `: ${sig.name.value}`;
            }
            html += `<div class="mark-tag"><i data-lucide="pen-tool" size="14"></i> ${label}</div>`;
        });
    }

    html += `</div>`;
    if (html.includes('mark-tag')) { // Only append if there are marks
        card.innerHTML = html;
        ui.resultsContainer.appendChild(card);
    }
}

function formatCurrency(value) {
    if (value == null) return '-';
    return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency: 'RUB',
        minimumFractionDigits: 2
    }).format(value);
}

function mapDocType(type) {
    const map = {
        'invoice_sf': 'Счет-фактура',
        'act_services': 'Акт выполненных работ',
        'upd': 'УПД',
        'other': 'Другой документ'
    };
    return map[type] || type;
}

function setLoading(state) {
    if (state) {
        ui.loader.classList.remove('hidden');
    } else {
        ui.loader.classList.add('hidden');
    }
}

function showModal(type) {
    if (type === 'raw') ui.modalRaw.classList.remove('hidden');
    if (type === 'json') ui.modalJson.classList.remove('hidden');
}

function resetApp() {
    currentFile = null;
    currentData = null;
    currentDocIndex = 0;
    ui.dashboard.classList.add('hidden');
    ui.uploadArea.classList.remove('hidden');
    ui.fileInput.value = ''; // clean input
}

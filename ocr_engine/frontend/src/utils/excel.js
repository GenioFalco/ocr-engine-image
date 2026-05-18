import * as XLSX from 'xlsx';

// ── Поиск значения по списку ключей (синонимов) ──────────────────────────────
const getValue = (flatData, keys) => {
    // 1. Точные совпадения (без учёта регистра и спецсимволов)
    for (const key of keys) {
        const nk = key.toLowerCase().replace(/[^a-zа-яё0-9]/g, '');
        for (const [rk, val] of Object.entries(flatData)) {
            if (rk.toLowerCase().replace(/[^a-zа-яё0-9]/g, '') === nk) {
                if (val !== null && val !== undefined && val !== '' && val !== 'null') return val;
            }
        }
    }
    // 2. Вхождения (ключ ≥ 3 символов)
    for (const key of keys) {
        const nk = key.toLowerCase().replace(/[^a-zа-яё0-9]/g, '');
        if (nk.length < 3) continue;
        for (const [rk, val] of Object.entries(flatData)) {
            if (rk.toLowerCase().replace(/[^a-zа-яё0-9]/g, '').includes(nk)) {
                if (val !== null && val !== undefined && val !== '' && val !== 'null') return val;
            }
        }
    }
    return '';
};

const parseFields = (fieldsObj) => {
    if (!fieldsObj) return {};
    const parsed = {};
    for (const [key, val] of Object.entries(fieldsObj)) {
        if (typeof val === 'string') {
            try { parsed[key] = JSON.parse(val); } catch { parsed[key] = val; }
        } else { parsed[key] = val; }
    }
    return parsed;
};

const flattenObject = (obj, prefix = '') => {
    const result = {};
    if (!obj || typeof obj !== 'object') return result;
    for (const [k, v] of Object.entries(obj)) {
        const key = prefix ? `${prefix} ${k}` : k;
        if (Array.isArray(v)) continue;
        if (v && typeof v === 'object' && 'value' in v) {
            const val = v.value;
            if (val !== null && val !== undefined) result[key] = String(val);
        } else if (v && typeof v === 'object') {
            Object.assign(result, flattenObject(v, key));
        } else if (v !== null && v !== undefined) {
            result[key] = String(v);
        }
    }
    return result;
};

// Находим самый большой массив (таблица товаров) — только если нет явного items
const findMainTable = (obj) => {
    let mainArr = [];
    const search = (item) => {
        if (Array.isArray(item)) {
            if (item.length > mainArr.length) mainArr = item;
            return;
        }
        if (item && typeof item === 'object' && !('value' in item)) {
            Object.values(item).forEach(search);
        }
    };
    search(obj);
    return mainArr;
};

// ── Маппинг внутренних имён типов документов → русские названия ──────────────
const DOC_TYPE_LABELS = {
    'UPD':             'Универсальный передаточный документ',
    'Act':             'Акт выполненных работ или оказание услуг',
    'Invoice':         'Счет на оплату или Invoice',
    'Invoice-Factura': 'Счет-фактура',
    'Torg12':          'Товарная накладная (ТОРГ-12)',
    'unknown':         'Неизвестный тип',
};
const getDocTypeLabel = (type) => DOC_TYPE_LABELS[type] || type || '-';

// ── Основная функция экспорта ─────────────────────────────────────────────────
// jobResults: Array<{ jobId: string, filename: string, documents: Array }>
export const exportClosingDocsToExcel = (jobResults) => {
    const rows = [];

    for (const { jobId, filename, documents } of jobResults) {
        for (const doc of (documents || [])) {
            const structured = parseFields(doc.fields || {});
            const { visual_marks: _vm, ...fieldsData } = structured;
            const flat = flattenObject(fieldsData);

            // Prefer explicit items key; fall back to findMainTable
            const tableArr = (Array.isArray(fieldsData.items) && fieldsData.items.length > 0)
                ? fieldsData.items
                : findMainTable(fieldsData);

            // ── Покупатель (ИНН) ──────────────────────────────────────────────
            const buyerINN = getValue(flat, [
                'buyer_inn', 'buyer inn', 'инн_покупателя', 'инн_заказчика', 'покупатель_инн',
            ]);

            // ── Продавец ──────────────────────────────────────────────────────
            const sellerName = getValue(flat, [
                'seller_name', 'seller name', 'наименование_продавца', 'имя_продавца',
                'исполнитель name', 'поставщик name',
            ]);
            const sellerINN = getValue(flat, [
                'seller_inn', 'seller inn', 'инн_продавца', 'инн_исполнителя',
                'продавца_инн', 'consignor_inn', 'consignor inn',
            ]);

            // ── Документ ──────────────────────────────────────────────────────
            const docNum  = getValue(flat, ['document_number', 'номер_документа', 'номер_счета', 'номер']);
            const docDate = getValue(flat, ['document_date', 'дата_документа', 'дата']);

            // Сумма: ищем total_with_vat раньше чем просто total (иначе попадает subtotal)
            const docSum = getValue(flat, [
                'total_with_vat', 'amounts total_with_vat', 'итого_с_ндс', 'сумма_с_ндс',
                'total_amount', 'amount', 'итого', 'сумма_документа',
            ]);

            // Ставка НДС — может быть только внутри items[0]
            const vatRate = getValue(flat, ['vat_rate', 'ставка_ндс', 'ндс_ставка'])
                || (tableArr.length > 0
                    ? getValue(flattenObject(tableArr[0]), ['vat_rate', 'ставка_ндс', 'ндс_ставка'])
                    : '');

            // Договор: basis_document type + number, или contract_title
            const basisType   = getValue(flat, ['basis_document type', 'basis document type', 'тип_основания']);
            const basisNumber = getValue(flat, [
                'basis_document number', 'basis document number',
                'contract_number', 'номер_договора', 'договор_номер',
            ]);
            const basisDate   = getValue(flat, ['basis_document date', 'basis document date', 'дата_договора']);
            const contractTitle = getValue(flat, ['contract_title', 'договор', 'основание']);

            let contractStr = contractTitle || '';
            if (!contractStr) {
                const parts = [basisType, basisNumber, basisDate ? `от ${basisDate}` : ''].filter(Boolean);
                contractStr = parts.join(' ');
            }

            // ── Таблица товаров ───────────────────────────────────────────────
            let tableString = '-';
            if (tableArr.length > 0) {
                tableString = tableArr.map(item => {
                    const f = flattenObject(item);
                    const name    = getValue(f, ['name', 'description', 'наименование', 'товар', 'услуга']) || '-';
                    const qty     = getValue(f, ['quantity', 'кол-во', 'количество', 'qty']) || '-';
                    const price   = getValue(f, ['price_without_vat', 'unit_price', 'price', 'цена']) || '-';
                    const sub     = getValue(f, ['amount_without_vat', 'subtotal', 'сумма_без_ндс']) || '-';
                    const itemVat = getValue(f, ['vat_rate', 'ставка_ндс', 'ндс_ставка']) || '-';
                    const tax     = getValue(f, ['vat_amount', 'сумма_налога', 'сумма_ндс', 'ндс']) || '-';
                    const total   = getValue(f, ['amount_with_vat', 'total_with_vat', 'total', 'итого']) || '-';
                    return `Наименование: ${name}, Кол-во: ${qty}, Цена: ${price}, Без НДС: ${sub}, НДС%: ${itemVat}, НДС: ${tax}, Итого: ${total}`;
                }).join(';\n');
            }

            // ── Описание (колонка 3) ──────────────────────────────────────────
            const description = [
                sellerName  ? `Контрагент: ${sellerName}`       : null,
                sellerINN   ? `ИНН продавца: ${sellerINN}`      : null,
                docNum      ? `Номер документа: ${docNum}`      : null,
                docDate     ? `Дата документа: ${docDate}`      : null,
                docSum      ? `Сумма с НДС: ${docSum}`          : null,
                vatRate     ? `Ставка НДС: ${vatRate}`          : null,
                contractStr ? `Договор: ${contractStr}`         : null,
                tableArr.length > 0 ? `\n${tableString}`        : null,
            ].filter(Boolean).join('\n');

            rows.push({
                'Вид документа':       getDocTypeLabel(doc.document_type),
                'Организация (ИНН покупателя)': buyerINN || '-',
                'Описание':            description || '-',
                'Файл':                filename || jobId || '-',
            });
        }
    }

    const worksheet = XLSX.utils.json_to_sheet(rows);
    const workbook  = XLSX.utils.book_new();

    // Ширина столбцов
    worksheet['!cols'] = [
        { wch: 20 },  // Вид документа
        { wch: 22 },  // Организация
        { wch: 90 },  // Описание
        { wch: 40 },  // Файл
    ];

    // Включаем перенос строк для столбца «Описание» (индекс 2)
    const range = XLSX.utils.decode_range(worksheet['!ref']);
    for (let R = range.s.r; R <= range.e.r; ++R) {
        const cell = worksheet[XLSX.utils.encode_cell({ r: R, c: 2 })];
        if (cell) {
            if (!cell.s) cell.s = {};
            cell.s.wrapText = true;
            cell.t = 's';
        }
    }

    XLSX.utils.book_append_sheet(workbook, worksheet, 'Отчет');
    const fileName = `Отчет_Закрывающие_${new Date().toLocaleDateString('ru-RU')}.xlsx`;
    XLSX.writeFile(workbook, fileName);
};

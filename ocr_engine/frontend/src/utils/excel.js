import * as XLSX from 'xlsx';

// ── Поиск значения по списку ключей (синонимов) ──────────────────────────
const getValue = (flatData, keys) => {
    // 1. Сначала ищем точные совпадения (без учета регистра и лишних символов)
    for (const key of keys) {
        const normalizedKey = key.toLowerCase().replace(/[^a-zа-яё0-9]/g, '');
        for (const [realKey, val] of Object.entries(flatData)) {
            const normalizedRealKey = realKey.toLowerCase().replace(/[^a-zа-яё0-9]/g, '');
            if (normalizedRealKey === normalizedKey) {
                if (val !== null && val !== undefined && val !== '' && val !== 'null') {
                    return val;
                }
            }
        }
    }
    // 2. Если не нашли точных, ищем вхождения
    for (const key of keys) {
        const normalizedKey = key.toLowerCase().replace(/[^a-zа-яё0-9]/g, '');
        if (normalizedKey.length < 3) continue; // слишком короткие ключи не ищем вхождением
        for (const [realKey, val] of Object.entries(flatData)) {
            const normalizedRealKey = realKey.toLowerCase().replace(/[^a-zа-яё0-9]/g, '');
            if (normalizedRealKey.includes(normalizedKey)) {
                if (val !== null && val !== undefined && val !== '' && val !== 'null') {
                    return val;
                }
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

// Находим самый большой массив (таблицу товаров)
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

export const exportClosingDocsToExcel = (documents) => {
    const rows = documents.map(doc => {
        const structured = parseFields(doc.fields || {});
        const flatData = flattenObject(structured);

        // --- Организация (ИНН Покупателя) ---
        const org = getValue(flatData, ['buyer_inn', 'инн_покупателя', 'инн_заказчика', 'покупатель_инн', 'buyer']);

        // --- Реквизиты Контрагента (Объединенная колонка) ---
        const contrINN = getValue(flatData, ['seller_inn', 'инн_продавца', 'инн_исполнителя', 'продавца_инн', 'seller']);
        const docNum = getValue(flatData, ['document_number', 'номер_документа', 'номер_счета', 'номер']);
        const docSum = getValue(flatData, ['total_amount', 'amount', 'total', 'сумма_документа', 'итого']);
        const contrNum = getValue(flatData, ['contract_number', 'номер_договора', 'договор_номер']);

        const combinedRequisites = [
            `Контрагент: ${contrINN || '-'}`,
            `Номер документа: ${docNum || '-'}`,
            `Сумма документа: ${docSum || '-'}`,
            `Номер договора: ${contrNum || '-'}`
        ].join('\n');

        // --- Остальные поля ---
        const docDate = getValue(flatData, ['document_date', 'дата_документа', 'дата']);
        const vatRate = getValue(flatData, ['vat_rate', 'ставка_ндс', 'ндс_ставка']);
        const contract = getValue(flatData, ['contract_title', 'договор', 'основание']);

        // --- Таблица товаров ---
        const tableArr = findMainTable(structured);
        let tableString = '';
        if (tableArr.length > 0) {
            tableString = tableArr.map(item => {
                const itemFlat = flattenObject(item);
                
                const name = getValue(itemFlat, ['name', 'description', 'наименование', 'товар', 'услуга']) || '-';
                const qty = getValue(itemFlat, ['quantity', 'кол-во', 'количество', 'колво', 'qty']) || '-';
                const price = getValue(itemFlat, ['price_without_vat', 'unit_price', 'price', 'цена']) || '-';
                const subtotal = getValue(itemFlat, ['amount_without_vat', 'subtotal', 'стоимость_безналога', 'сумма_без_ндс', 'сумма']) || '-';
                const itemVat = getValue(itemFlat, ['vat_rate', 'ставка_ндс', 'ндс_ставка']) || '-';
                const tax = getValue(itemFlat, ['vat_amount', 'сумма_налога', 'сумма_ндс', 'ндс']) || '-';
                const total = getValue(itemFlat, ['amount_with_vat', 'total', 'total_amount', 'стоимость_с_налогами', 'итого']) || '-';

                return `Наименование: ${name}, Кол-во: ${qty}, Цена: ${price}, Стоимость без налога: ${subtotal}, Ставка НДС: ${itemVat}, Сумма налога: ${tax}, Стоимость с налогами: ${total}`;
            }).join(' ;\n');
        }

        return {
            'Организация': org || '-',
            'Реквизиты Контрагента': combinedRequisites,
            'Дата документа': docDate || '-',
            'Ставка НДС': vatRate || '-',
            'Договор': contract || '-',
            'Вид документа': doc.document_type || '-',
            'Таблица': tableString || '-'
        };
    });

    const worksheet = XLSX.utils.json_to_sheet(rows);
    const workbook = XLSX.utils.book_new();

    // Настройка колонок (ширина)
    worksheet['!cols'] = [
        { wch: 20 }, // Организация
        { wch: 40 }, // Реквизиты
        { wch: 15 }, // Дата
        { wch: 15 }, // НДС
        { wch: 25 }, // Договор
        { wch: 20 }, // Вид
        { wch: 100 }, // Таблица
    ];

    // Включаем перенос строк (\n)
    const range = XLSX.utils.decode_range(worksheet['!ref']);
    for (let R = range.s.r; R <= range.e.r; ++R) {
        [1, 6].forEach(C => {
            const cell = worksheet[XLSX.utils.encode_cell({ r: R, c: C })];
            if (cell) {
                if (!cell.s) cell.s = {};
                cell.s.wrapText = true;
                cell.t = 's';
            }
        });
    }

    XLSX.utils.book_append_sheet(workbook, worksheet, 'Отчет');
    const fileName = `Отчет_Закрывающие_${new Date().toLocaleDateString('ru-RU')}.xlsx`;
    XLSX.writeFile(workbook, fileName);
};

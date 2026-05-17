import base64
import json
import logging
import re
from typing import List, Dict, Any, Optional
from app.providers.base_llm import BaseLLM, ClassificationResult, ExtractionResult

try:
    from openai import OpenAI
except ImportError as e:
    OpenAI = None

logger = logging.getLogger(__name__)

class QwenProvider(BaseLLM):
    """
    Direct Qwen provider via DashScope's OpenAI compatible API endpoint.
    Base URL: https://dashscope-intl.aliyuncs.com/compatible-mode/v1
    """
    def __init__(self, api_key: str, model: str = "qwen-vl-max-latest", temperature: float = 0.1, max_tokens: int = 8192):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = min(max_tokens, 8192)  # Qwen VL Max API hard limit = 8192
        if OpenAI:
            # Pointing the OpenAI client to Qwen's DashScope compatible API (International Region)
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
                timeout=120.0  # 2 minutes max — prevent indefinite hang
            )
        else:
            self.client = None
            logger.error("OpenAI library is not installed. QwenProvider cannot function.")

    def _encode_image(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def _prepare_image_message(self, prompt: str, image_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Qwen-VL format is exactly the same as OpenAI's vision format
        content = [{"type": "text", "text": prompt}]
        for img in image_data:
            if "bytes" in img:
                base64_str = base64.b64encode(img["bytes"]).decode("utf-8")
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{base64_str}"
                    }
                })
        return content

    def classify_page(self, image_path: str, document_types: Optional[List[Dict[str, str]]] = None) -> ClassificationResult:
        if not self.client:
            return ClassificationResult(document_type="error", confidence=0.0, raw_response="OpenAI lib missing")

        try:
            prompt = """
Классифицируй этот документ.
Ответь ТОЛЬКО JSON-объектом в таком формате и больше ничего:
{
  "document_type": "название_типа",
  "confidence": 0.99
}
Если тип неизвестен, укажи "unknown".
"""
            if document_types:
                types_desc = "\\n".join([f"- {dt.get('name', 'unknown')}: {dt.get('description', '')}" for dt in document_types])
                prompt += f"\\nДоступные типы документов:\\n{types_desc}"

            base64_img = self._encode_image(image_path)
            content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}}
            ]

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": content}],
                temperature=self.temperature,
                max_tokens=200
            )
            
            resp_content = response.choices[0].message.content
            raw_response = resp_content
            
            resp_content = resp_content.replace("```json", "").replace("```", "").strip()
            data = json.loads(resp_content)
            
            return ClassificationResult(
                document_type=data.get("document_type", "unknown"),
                confidence=float(data.get("confidence", 0.0)),
                raw_response=raw_response
            )
        except Exception as e:
            logger.error(f"Qwen classification error: {e}")
            return ClassificationResult(document_type="error", confidence=0.0, raw_response=f"Error: {e}")

    def classify_document(self, image_paths: List[str], document_types: Optional[List[Dict[str, str]]] = None) -> ClassificationResult:
        if not image_paths:
             return ClassificationResult(document_type="unknown", confidence=0.0)
        return self.classify_page(image_paths[0], document_types)

    def _recover_partial_items(self, raw_str: str) -> list:
        """Парсит все полные JSON-объекты из обрезанного массива (спасает items при truncation)."""
        items = []
        depth = 0
        start = None
        for i, ch in enumerate(raw_str):
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start is not None:
                    try:
                        obj = json.loads(raw_str[start:i + 1])
                        items.append(obj)
                    except Exception:
                        pass
                    start = None
        return items

    def _build_extraction_prompt(self, schema_str: str, include_items: bool = True) -> str:
        items_note = (
            "• items: только реальные позиции товаров/услуг, не заголовки и не итоги. Максимум 30 строк."
            if include_items else
            "• НЕ извлекай строки таблицы товаров/услуг (поле items). Оставь items пустым массивом []."
        )
        return f"""
Извлеки данные из документа и верни их строго в формате JSON-схемы ниже. Только то, что реально видишь на изображении.

СХЕМА:
{schema_str}

═══ ПРАВИЛА ИЗВЛЕЧЕНИЯ ═══

【НОМЕР И ДАТА ДОКУМЕНТА】
• document_number = номер из ЗАГОЛОВКА документа (например, "Счёт-фактура № 77-40" → "77-40")
  НЕ путай с: кодами товаров, номерами строк таблицы, кодами ОКПД, номерами договора
• document_date = дата из заголовка документа. НЕ дата договора-основания.

【ПРОДАВЕЦ И ПОКУПАТЕЛЬ — ЧИТАЙ МЕТКИ БУКВАЛЬНО】
• seller = тот, кто указан в строке "Продавец:" (в счёт-фактуре/УПД) или "Исполнитель:"/"Поставщик:" (в актах)
• buyer  = тот, кто указан в строке "Покупатель:" или "Заказчик:"
• Не меняй их местами! ИНН из строки "Продавец:" → только в seller.inn

【ИНН И КПП】
• В российских документах строки выглядят так:
  "ИНН/КПП продавца: 3305051742/330501001"  → inn продавца = "3305051742", kpp продавца = "330501001"
  "ИНН/КПП покупателя: 3305051742/330501001" → inn покупателя = "3305051742", kpp покупателя = "330501001"
  "ИНН/КПП: 3305051742/330501001"            → аналогично, по контексту (продавец или покупатель)
• Число ДО знака "/" → это ИНН (пиши в inn). Число ПОСЛЕ "/" → это КПП (пиши в kpp).
• НЕ сливай ИНН и КПП в одно поле!
• Иногда КПП отсутствует (например, у ИП): строка выглядит как "ИНН: 753604922702" — тогда kpp = null.
• Определяй тип числа по количеству цифр:
  - 10 цифр → ИНН юридического лица (ООО, АО и т.д.)
  - 12 цифр → ИНН физического лица / ИП
  - 9 цифр  → КПП
  - 6 цифр  → почтовый индекс (часть адреса, НЕ ИНН!)
• Переписывай каждую цифру точно, не угадывай. Часто путают: 3↔8, 0↔6, 1↔7.
• Не можешь прочитать точно → пиши null

【ДОГОВОР-ОСНОВАНИЕ】
• Поля basis_document.number и basis_document.date — это реквизиты ДОГОВОРА из строки "К договору №..."
  НЕ путай с номером/датой самого документа!

【ДАННЫЕ В ПОЛЯХ】
• name — только название организации/ИП, без адреса и реквизитов
• address — полный адрес включая индекс
• Числа (суммы, ИНН) — переписывай цифра за цифрой, не округляй
{items_note}
• raw_text — верни пустой строкой ""
• Поле отсутствует на скане → пиши null

Верни ТОЛЬКО JSON-объект без каких-либо пояснений и без ```json.
        """

    def extract_document(self, images_data: List[Dict[str, Any]], json_schema: Dict[str, Any]) -> ExtractionResult:
        if not self.client:
            logger.warning("Qwen client not initialized.")
            return ExtractionResult(fields={}, stamps=[], signatures=[], raw_response="{}")

        # Определяем: есть ли в схеме поле items (таблица строк)?
        # Ищем рекурсивно, т.к. схема может быть вложенной
        def _has_items_field(obj, depth=0):
            if depth > 6:
                return False
            if isinstance(obj, dict):
                if "items" in obj:
                    return True
                return any(_has_items_field(v, depth + 1) for v in obj.values())
            if isinstance(obj, list):
                return any(_has_items_field(item, depth + 1) for item in obj)
            return False
        schema_has_items = _has_items_field(json_schema)
        logger.debug(f"schema_has_items={schema_has_items} for schema keys: {list(json_schema.keys()) if isinstance(json_schema, dict) else type(json_schema)}")

        try:
            limited_data = images_data[:10]
            schema_str = json.dumps(json_schema, ensure_ascii=False, indent=2)

            # ── Проход 1: шапка документа ───────────────────────────────────
            # Если в схеме есть items — сразу просим НЕ извлекать их (отдельный проход),
            # чтобы шапка гарантированно вошла в 8192 токенов.
            prompt = self._build_extraction_prompt(schema_str, include_items=not schema_has_items)
            message_content = self._prepare_image_message(prompt, limited_data)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": message_content}],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            finish_reason = response.choices[0].finish_reason
            resp_content = response.choices[0].message.content
            raw_response = resp_content

            if finish_reason == "length":
                logger.warning(
                    f"Qwen PASS-1 TRUNCATED (finish_reason=length, max_tokens={self.max_tokens}). "
                    "Шапка документа обрезана — запускаем повторный проход только для шапки..."
                )
                # Повторный проход для шапки с явным запретом items
                try:
                    header_prompt = self._build_extraction_prompt(schema_str, include_items=False)
                    header_content = self._prepare_image_message(header_prompt, limited_data)
                    header_resp = self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": header_content}],
                        temperature=self.temperature,
                        max_tokens=self.max_tokens
                    )
                    resp_content = header_resp.choices[0].message.content or resp_content
                    raw_response = resp_content
                    logger.info("Повторный проход шапки завершён.")
                except Exception as header_err:
                    logger.warning(f"Повторный проход шапки не удался: {header_err}")
                # Если PASS-1 обрезан — значит документ большой, items точно есть
                schema_has_items = True

            # ── Проход 2: строки таблицы (items) ────────────────────────────
            _recovered_items = None
            if schema_has_items:
                try:
                    items_prompt = (
                        "Извлеки ТОЛЬКО строки таблицы товаров/услуг из документа.\n"
                        "Верни JSON-массив объектов, каждый объект — одна строка таблицы.\n"
                        "Поля: name (наименование), quantity (кол-во), unit (ед.изм.), "
                        "price (цена), amount (сумма), vat_rate (ставка НДС), vat_amount (НДС).\n"
                        "Только реальные позиции товаров/услуг, без заголовков и итогов. Максимум 50 строк.\n"
                        "Верни ТОЛЬКО JSON-массив без пояснений."
                    )
                    items_content = self._prepare_image_message(items_prompt, limited_data)
                    items_resp = self.client.chat.completions.create(
                        model=self.model,
                        messages=[{"role": "user", "content": items_content}],
                        temperature=self.temperature,
                        max_tokens=self.max_tokens
                    )
                    items_raw = items_resp.choices[0].message.content or ""
                    items_finish = items_resp.choices[0].finish_reason
                    items_raw = items_raw.replace("```json", "").replace("```", "").strip()

                    if items_finish == "length":
                        logger.warning("Qwen PASS-2 (items) TRUNCATED — парсим частично.")
                        _recovered_items = self._recover_partial_items(items_raw)
                        logger.info(f"Частичное восстановление items: {len(_recovered_items)} строк.")
                    else:
                        try:
                            items_data = json.loads(items_raw)
                            if isinstance(items_data, list):
                                _recovered_items = items_data
                            else:
                                _recovered_items = None
                        except Exception:
                            # JSON сломан — пробуем частичный парсер
                            _recovered_items = self._recover_partial_items(items_raw)
                            logger.warning(f"Items JSON broken, partial recovery: {len(_recovered_items)} строк.")

                    if _recovered_items is not None:
                        logger.info(f"Проход 2 (items): извлечено {len(_recovered_items)} строк таблицы.")
                except Exception as items_err:
                    logger.warning(f"Проход 2 (items) не удался: {items_err}")
                    _recovered_items = None

            resp_content = resp_content.replace("```json", "").replace("```", "").strip()
            if resp_content.startswith("[") and resp_content.endswith("]"):
                resp_content = resp_content[1:-1].strip()

            try:
                data = json.loads(resp_content)
            except Exception as e:
                logger.error(f"Qwen JSON Decode Error: {e}. Attempting partial recovery...")
                data = {}
                try:
                    m = re.search(r'"structured"\s*:\s*(\{.*)', resp_content, re.DOTALL)
                    if m:
                        struct_str = m.group(1)
                        depth = 0
                        end_idx = 0
                        for i, ch in enumerate(struct_str):
                            if ch == '{': depth += 1
                            elif ch == '}':
                                depth -= 1
                                if depth == 0:
                                    end_idx = i + 1
                                    break
                        if end_idx > 0:
                            recovered = json.loads(struct_str[:end_idx])
                            data = recovered
                            logger.warning("Partial JSON recovery succeeded (extracted 'structured' block).")
                        else:
                            # Heuristic: try to forcefully close the JSON if depth > 0
                            fixed_str = struct_str + ("}" * depth)
                            try:
                                recovered = json.loads(fixed_str)
                                data = recovered
                                logger.warning("Partial JSON recovery succeeded via forced brace closure.")
                            except Exception as e2:
                                # Final try: chop off trailing incomplete string before closing braces
                                clean_str = re.sub(r'"[^"]*$', '', struct_str)
                                clean_str = re.sub(r'[,:]\s*$', '', clean_str)
                                fixed_str_2 = clean_str + ("}" * depth) + "]}"
                                try:
                                    recovered = json.loads(fixed_str_2)
                                    data = recovered
                                    logger.warning("Partial JSON recovery succeeded via aggressive truncation.")
                                except Exception:
                                    pass
                except Exception as rec_e:
                    logger.warning(f"Partial JSON recovery also failed: {rec_e}")

            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            elif not isinstance(data, dict):
                data = {}

            # Unwrap "documents" array if the LLM wrapped the response
            if "documents" in data and isinstance(data["documents"], list) and len(data["documents"]) > 0:
                data = data["documents"][0]

            # Вставляем items из второго прохода
            if _recovered_items is not None:
                data["items"] = _recovered_items
                logger.info(f"Items из прохода 2 вставлены в результат: {len(_recovered_items)} шт.")
            
            stamps = []
            signatures = []
            if "visual_marks" in data:
                 visual_marks = data.pop("visual_marks", {})
                 if isinstance(visual_marks, dict):
                     stamps = visual_marks.get("seals", [])
                     signatures = visual_marks.get("signatures", [])
                     
            if not isinstance(stamps, list): stamps = []
            if not isinstance(signatures, list): signatures = []

            # Now unwrap the actual fields
            if "structured" in data and isinstance(data["structured"], dict):
                data = data["structured"]
            elif "fields" in data and isinstance(data["fields"], dict):
                data = data["fields"]

            # Second-pass: pop visual_marks if LLM put them inside structured/fields
            if "visual_marks" in data:
                vmarks2 = data.pop("visual_marks", {})
                if isinstance(vmarks2, dict):
                    extra_stamps = vmarks2.get("seals", [])
                    extra_sigs   = vmarks2.get("signatures", [])
                    if isinstance(extra_stamps, list): stamps.extend(extra_stamps)
                    if isinstance(extra_sigs,   list): signatures.extend(extra_sigs)

            for s in stamps:
                if isinstance(s, str):
                    stamps[stamps.index(s)] = {"value": s}
            for s in signatures:
                if isinstance(s, str):
                    signatures[signatures.index(s)] = {"value": s}

            tokens_used = 0
            input_tokens = 0
            output_tokens = 0
            try:
                input_tokens  = response.usage.prompt_tokens or 0
                output_tokens = response.usage.completion_tokens or 0
                tokens_used   = response.usage.total_tokens or (input_tokens + output_tokens)
            except Exception:
                pass

            return ExtractionResult(
                fields=data,
                stamps=stamps,
                signatures=signatures,
                raw_response=raw_response,
                tokens_used=tokens_used,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        except Exception as e:
            logger.error(f"Qwen extraction error: {e}")
            return ExtractionResult(fields={}, stamps=[], signatures=[], raw_response=f"Error: {e}")

    def validate_extraction(self, extraction_result: ExtractionResult, images_data: List[Dict[str, Any]]) -> bool:
        if not extraction_result.fields:
            return False

        data = extraction_result.fields
        if not data.get("document_date") and not data.get("document_number") and not data.get("amounts"):
             return False
        return True

    def extract_raw_text(self, images_data: List[Dict[str, Any]]) -> str:
        """Extract all text from document pages (sent together) using Qwen VL.
        Returns a single string with all text from all pages."""
        if not self.client:
            return ""
        try:
            num_pages = len(images_data)
            page_hint = f"Документ содержит {num_pages} стр." if num_pages > 1 else "Документ — 1 страница."
            prompt = (
                f"{page_hint} "
                "Извлеки ВЕСЬ текст со всех страниц документа дословно, сохраняя структуру строк и абзацев. "
                "Включай: печатный текст, рукописный текст, текст в таблицах, заголовки, подписи, штампы — всё что видишь. "
                "Если текст нечёткий или рукописный — пиши максимально точно как можешь прочитать. "
                "Если несколько страниц — разделяй их строкой вида '=== Страница N ==='. "
                "Верни ТОЛЬКО сам текст. Без пояснений, без преамбул, без markdown."
            )
            message_content = self._prepare_image_message(prompt, images_data)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": message_content}],
                temperature=0.0,
                max_tokens=self.max_tokens
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"Qwen extract_raw_text error: {e}")
            return f"[Ошибка извлечения текста: {e}]"

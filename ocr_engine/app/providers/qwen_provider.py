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
    def __init__(self, api_key: str, model: str = "qwen-vl-max-latest", temperature: float = 0.1, max_tokens: int = 8000):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = min(max_tokens, 8192)
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

    def extract_document(self, images_data: List[Dict[str, Any]], json_schema: Dict[str, Any]) -> ExtractionResult:
        if not self.client:
            logger.warning("Qwen client not initialized.")
            return ExtractionResult(fields={}, stamps=[], signatures=[], raw_response="{}")

        try:
            limited_data = images_data[:10]
            schema_str = json.dumps(json_schema, ensure_ascii=False, indent=2)

            prompt = f"""
Твоя задача — извлечь данные из предоставленных страниц документа строго в соответствии с JSON схемой, не меняя структуру.
СХЕМА JSON (JSON Schema):
{schema_str}

ПРАВИЛА НАПИСАНИЯ ОТВЕТА (ОЧЕНЬ ВАЖНО):
1. ПИШИ ТОЛЬКО ТО, ЧТО ВИДИШЬ СВОИМИ ГЛАЗАМИ НА КАРТИНКАХ. ЗАПРЕЩЕНО ВЫДУМЫВАТЬ ИЛИ ГЕНЕРИРОВАТЬ ПРИМЕРЫ!
2. ЧИСТОТА ДАННЫХ:
   - В поле `name` (название) пиши ТОЛЬКО название компании/ИП (без адреса, без реквизитов!). Адрес пиши СТРОГО в поле `address`. Не смешивай их.
   - В полях типа `document_number` (номер документа) пиши ТОЛЬКО сами цифры/буквы номера. Без символа "№", без слова "номер".
   - В массив `items` (список товаров/услуг) добавляй ТОЛЬКО реальные строки с конкретными позициями. КАТЕГОРИЧЕСКИ игнорируй заголовки таблиц, подзаголовки групп (например, "Выполненные работы:", "Товары:") и итоговые строки.
   - ОГРАНИЧЕНИЕ ДЛИНЫ: Если в документе огромная таблица (более 30 позиций), извлеки ТОЛЬКО ПЕРВЫЕ 30 строк. НЕ извлекай сотни строк, иначе твой ответ оборвется из-за лимита токенов, и JSON будет сломан!
3. ЦИФРОВЫЕ ПОЛЯ — ПЕРЕПИСЫВАЙ ДОСЛОВНО (КРИТИЧЕСКИ ВАЖНО):
   - Любое числовое поле (ИНН, КПП, номер счёта, сумма) переписывай ЦИФРА ЗА ЦИФРОЙ точно как видишь.
   - НЕ округляй, НЕ исправляй, НЕ угадывай цифры — если цифра нечёткая, смотри на неё внимательнее.
   - Особенно часто путают: 3↔8, 0↔6, 1↔7, 5↔6 — будь внимателен к каждой цифре.
4. ПРАВИЛА ДЛЯ ИНН / КПП (КРИТИЧЕСКИ ВАЖНО — НЕ ПУТАЙ):
   - ИНН юридического лица = РОВНО 10 цифр (например: 7701234567)
   - ИНН физического лица / ИП = РОВНО 12 цифр (например: 770112345678)
   - КПП = РОВНО 9 цифр (например: 770101001)
   - ПОЧТОВЫЙ ИНДЕКС = РОВНО 6 цифр (например: 601900) — это ЧАСТЬ АДРЕСА, НИКОГДА не пиши индекс в поле `inn` или `kpp`!
   - Если в адресе стоит 6-значное число — это индекс, пиши его в поле `address`, НЕ в `inn`.
   - Если не можешь точно определить ИНН или КПП — пиши `null`, не угадывай.
5. ЗАПРЕЩАЕТСЯ писать "ООО 'Пример'", "123456789" и любые тестовые данные. Если на скане нет реального поля, пиши `null`.
6. Верни чистый JSON-объект, строго соответствующий схеме. Обязательно соблюдай структуру иерархии.
7. ВАЖНО: Если в схеме есть поле `raw_text`, ты ОБЯЗАН вернуть его ПУСТЫМ (""). КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО извлекать весь текст документа.
8. Верни ТОЛЬКО JSON-объект. Больше ни единого слова, без преамбул. Без маркдауна (без ```json).
9. КРИТИЧЕСКИ ВАЖНО — ПРОДАВЕЦ И ПОКУПАТЕЛЬ (НЕ ПУТАЙ!):
   - Поле `seller` (продавец/исполнитель/поставщик) = тот, КТО ВЫСТАВЛЯЕТ документ:
     * В счёт-фактуре / УПД: строка "Продавец:" в документе → seller
     * В акте / накладной: строка "Исполнитель:" или "Поставщик:" → seller
   - Поле `buyer` (покупатель/заказчик) = тот, КОМУ выставляется документ:
     * В счёт-фактуре / УПД: строка "Покупатель:" в документе → buyer
     * В акте / накладной: строка "Заказчик:" или "Покупатель:" → buyer
   - ЧИТАЙ МЕТКИ В ДОКУМЕНТЕ БУКВАЛЬНО. "Продавец:" → seller, "Покупатель:" → buyer. Не меняй их местами ни при каких обстоятельствах!
   - ИНН продавца пиши ТОЛЬКО в seller.inn, ИНН покупателя — ТОЛЬКО в buyer.inn. Не перекладывай ИНН между полями!
            """
            
            message_content = self._prepare_image_message(prompt, limited_data)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": message_content}],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            resp_content = response.choices[0].message.content
            raw_response = resp_content
            
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
            try:
                tokens_used = response.usage.total_tokens or 0
            except Exception:
                pass

            return ExtractionResult(
                fields=data,
                stamps=stamps,
                signatures=signatures,
                raw_response=raw_response,
                tokens_used=tokens_used
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

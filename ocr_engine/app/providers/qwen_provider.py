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
• Строка "ИНН/КПП: 3305051742/330501001":
  - до "/" → ИНН (пиши в поле inn)
  - после "/" → КПП (пиши в поле kpp)
  - НЕ сливай их вместе!
• ИНН юрлица = ровно 10 цифр | ИНН ИП = ровно 12 цифр | КПП = ровно 9 цифр
• Почтовый индекс = 6 цифр в начале адреса — это НЕ ИНН, пиши его в поле address
• Не можешь прочитать точно → пиши null

【ДОГОВОР-ОСНОВАНИЕ】
• Поля basis_document.number и basis_document.date — это реквизиты ДОГОВОРА из строки "К договору №..."
  НЕ путай с номером/датой самого документа!

【ДАННЫЕ В ПОЛЯХ】
• name — только название организации/ИП, без адреса и реквизитов
• address — полный адрес включая индекс
• Числа (суммы, ИНН) — переписывай цифра за цифрой, не округляй
• items: только реальные позиции товаров/услуг, не заголовки и не итоги. Максимум 30 строк.
• raw_text — верни пустой строкой ""
• Поле отсутствует на скане → пиши null

Верни ТОЛЬКО JSON-объект без каких-либо пояснений и без ```json.
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

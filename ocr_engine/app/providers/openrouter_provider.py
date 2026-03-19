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
    logger.error(f"OpenAI import error: {e}")

logger = logging.getLogger(__name__)

class OpenRouterProvider(BaseLLM):
    def __init__(self, api_key: str, model: str = "qwen/qwen3-235b-a22b-thinking-2507", temperature: float = 0.1, max_tokens: int = 8000):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        if OpenAI and api_key:
            try:
                self.client = OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=api_key,
                    timeout=180.0 # Prevent early timeouts for large vision requests
                )
            except Exception as e:
                logger.error(f"Failed to initialize OpenRouter client: {e}")
                self.client = None
        else:
            self.client = None
            logger.error("OpenAI library not installed or API key missing.")

    def _prepare_image_message(self, prompt: str, images_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        content = [{"type": "text", "text": prompt}]
        for img in images_data:
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
            logger.warning("OpenRouter client not initialized.")
            return ClassificationResult(document_type="unknown", confidence=0.0)

        try:
            with open(image_path, "rb") as f:
                img_bytes = f.read()

            if document_types:
                types_str = ", ".join([f'"{dt["name"]}"' for dt in document_types])
                descriptions = "\n".join([f'- "{dt["name"]}": {dt.get("description", "")}' for dt in document_types])
                
                type_instruction = f"""
Выбери ТИП ДОКУМЕНТА из списка: {types_str} или "unknown".
Описания:
{descriptions}

ПРАВИЛА:
1. Смотри на ЗАГОЛОВОК ("Акт", "УПД", "Счет-фактура" и т.д.).
2. Акт — это строго Акт. УПД — это строго УПД. Не путай их.
3. Верни точный ID типа.
                """
            else:
                types_str = '"unknown"'
                type_instruction = 'Типы не заданы. Верни "unknown".'

            prompt = f"""{type_instruction}\nВерни ТОЛЬКО JSON. Без маркдауна (```json).\n{{"document_type": "string", "confidence": 0.0-1.0}}"""
            
            message_content = self._prepare_image_message(prompt, [{"bytes": img_bytes}])
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": message_content}],
                temperature=self.temperature,
                max_tokens=200
            )
            
            content = response.choices[0].message.content
            raw_response = content
            
            content = content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
            
            return ClassificationResult(
                document_type=data.get("document_type", "unknown"),
                confidence=float(data.get("confidence", 0.0)),
                raw_response=raw_response
            )

        except Exception as e:
            logger.error(f"OpenRouter classification error: {e}")
            return ClassificationResult(document_type="error", confidence=0.0, raw_response=f"Error: {e}")

    def classify_document(self, image_paths: List[str], document_types: Optional[List[Dict[str, str]]] = None) -> ClassificationResult:
        if not image_paths:
             return ClassificationResult(document_type="unknown", confidence=0.0)
        return self.classify_page(image_paths[0], document_types)

    def extract_document(self, images_data: List[Dict[str, Any]], json_schema: Dict[str, Any]) -> ExtractionResult:
        if not self.client:
            logger.warning("OpenRouter client not initialized.")
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
   - В ИНН и КПП пиши строго цифры.
   - В массив `items` (список товаров/услуг) добавляй ТОЛЬКО реальные строки с конкретными позициями. КАТЕГОРИЧЕСКИ игнорируй заголовки таблиц, подзаголовки групп (например, "Выполненные работы:", "Товары:") и итоговые строки.
3. ЗАПРЕЩАЕТСЯ писать "ООО 'Пример'", "123456789" и любые тестовые данные. Если на скане нет реального поля, пиши `null`.
4. Верни чистый JSON-объект, строго соответствующий схеме. Обязательно соблюдай структуру иерархии (не прячь ответ внутрь сторонних полей).
5. ВАЖНО: Если в схеме есть поле `raw_text`, ты ОБЯЗАН вернуть его ПУСТЫМ (""). КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО извлекать весь текст документа.
6. Верни ТОЛЬКО JSON-объект. Больше ни единого слова, без преамбул. Без маркдауна (без ```json).
            """
            
            message_content = self._prepare_image_message(prompt, limited_data)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": message_content}],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            content = response.choices[0].message.content
            raw_response = content
            
            content = content.replace("```json", "").replace("```", "").strip()
            if content.startswith("[") and content.endswith("]"):
                content = content[1:-1].strip()
                
            try:
                data = json.loads(content)
            except Exception as e:
                logger.error(f"OpenRouter JSON Decode Error: {e}. Attempting partial recovery...")
                # Try to recover first document from a truncated JSON response
                data = {}
                try:
                    # Find the first complete JSON object in the response (handles truncated arrays)
                    # Try to find the "structured" block of the first document
                    m = re.search(r'"structured"\s*:\s*(\{.*)', content, re.DOTALL)
                    if m:
                        struct_str = m.group(1)
                        # Balance braces to get just the first complete object
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

            for s in stamps:
                if isinstance(s, str):
                    stamps[stamps.index(s)] = {"value": s}
            for s in signatures:
                if isinstance(s, str):
                    signatures[signatures.index(s)] = {"value": s}

            return ExtractionResult(
                fields=data,
                stamps=stamps,
                signatures=signatures,
                raw_response=raw_response
            )

        except Exception as e:
            logger.error(f"OpenRouter extraction error: {e}")
            return ExtractionResult(fields={}, stamps=[], signatures=[], raw_response=f"Error: {e}")

    def validate_extraction(self, extraction_result: ExtractionResult, images_data: List[Dict[str, Any]]) -> bool:
        if not extraction_result.fields:
            return False
            
        data = extraction_result.fields
        if not data.get("document_date") and not data.get("document_number") and not data.get("amounts"):
             return False
        return True

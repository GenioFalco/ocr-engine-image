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
        self.max_tokens = max_tokens
        if OpenAI:
            # Pointing the OpenAI client to Qwen's DashScope compatible API (International Region)
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
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
        for item in image_data:
            if item.get("type") == "image_url":
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": item["image_url"]["url"]
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
2. ЗАПРЕЩАЕТСЯ писать "ООО 'Пример'", "123456789", "ООО 'СпецСтрой'" и любые другие тестовые данные. Если на скане нет реального ИНН или названия, пиши `null`.
3. Верни чистый JSON-объект, строго соответствующий схеме. Обязательно соблюдай структуру иерархии.
4. ВАЖНО: Если в схеме есть поле `raw_text`, ты ОБЯЗАН вернуть его ПУСТЫМ (""). КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО извлекать весь текст документа.
5. Верни ТОЛЬКО JSON-объект. Больше ни единого слова, без преамбул. Без маркдауна (без ```json).
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
                except Exception as rec_e:
                    logger.warning(f"Partial JSON recovery also failed: {rec_e}")

            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            elif not isinstance(data, dict):
                data = {}
                
            if "structured" in data and isinstance(data["structured"], dict):
                data = data["structured"]
            elif "fields" in data and isinstance(data["fields"], dict):
                data = data["fields"]
            
            stamps = []
            signatures = []
            if "visual_marks" in data:
                 visual_marks = data.pop("visual_marks", {})
                 if isinstance(visual_marks, dict):
                     stamps = visual_marks.get("seals", [])
                     signatures = visual_marks.get("signatures", [])
                     
            if not isinstance(stamps, list): stamps = []
            if not isinstance(signatures, list): signatures = []

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
            logger.error(f"Qwen extraction error: {e}")
            return ExtractionResult(fields={}, stamps=[], signatures=[], raw_response=f"Error: {e}")

    def validate_extraction(self, extraction_result: ExtractionResult, images_data: List[Dict[str, Any]]) -> bool:
        if not extraction_result.fields:
            return False
            
        data = extraction_result.fields
        if not data.get("document_date") and not data.get("document_number") and not data.get("amounts"):
             return False
        return True

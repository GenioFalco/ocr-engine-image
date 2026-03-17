from typing import List, Dict, Any, Optional
import os
import json
import base64
import logging
from app.providers.base_llm import BaseLLM, ClassificationResult, ExtractionResult

try:
    from gigachat import GigaChat
    # Import necessary models. Note: MessagesContentImage is NOT used in 0.2.0 for this workflow
    from gigachat.models import Chat, Messages, MessagesRole
except ImportError as e:
    GigaChat = None
    GigaChat = None
    logger.error(f"GigaChat import error: {e}")

logger = logging.getLogger(__name__)

class GigaChatProvider(BaseLLM):
    def __init__(self, api_key: str, model: str = "GigaChat-2-Pro", temperature: float = 0.1):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.client = None
        
        # DEBUG LOGGING
        # logger.info(f"Initializing GigaChatProvider with key length: {len(api_key) if api_key else 0}")

        if GigaChat and api_key:
            try:
                # Disable SSL verification for development if needed, strict check in prod
                self.client = GigaChat(credentials=api_key, verify_ssl_certs=False, timeout=600)
            except Exception as e:
                logger.error(f"Failed to initialize GigaChat client: {e}")
                logger.error(f"Failed to initialize GigaChat client: {e}")
        else:
             logger.warning("GigaChat client NOT initialized: Missing credentials or library.")

    def _upload_image_bytes(self, image_bytes: bytes, filename: str) -> Optional[str]:
        """Uploads image to GigaChat from memory and returns the file ID."""
        if not self.client:
            return None
        
        try:
            logger.info(f"Uploading image bytes: {filename}")
            import io
            import time
            
            # Add retry loop to prevent network failures during parallel multi-document uploads
            last_error = None
            for attempt in range(3):
                try:
                    # GigaChat client accepts a tuple of (filename, file_like_object)
                    uploaded_file = self.client.upload_file(file=(filename, io.BytesIO(image_bytes)), purpose="general")
                    
                    if hasattr(uploaded_file, 'id_'):
                        return uploaded_file.id_
                    elif hasattr(uploaded_file, 'id'):
                        return uploaded_file.id
                    
                    try:
                        return uploaded_file.model_dump().get("id") or uploaded_file.model_dump().get("id_")
                    except:
                        pass
                        
                    logger.error(f"Could not find ID in uploaded file object: {dir(uploaded_file)}")
                    return None
                except Exception as e:
                    last_error = e
                    logger.warning(f"Upload attempt {attempt+1} failed for {filename}: {e}. Retrying in 1.5s...")
                    time.sleep(1.5)
            
            logger.error(f"Failed to upload image {filename} after 3 attempts. Last error: {last_error}")
            return None
        except Exception as e:
            logger.error(f"Critical error during image upload {filename}: {e}")
            return None

    def _upload_image(self, image_path: str) -> Optional[str]:
        """Uploads image to GigaChat and returns the file ID."""
        if not self.client:
            return None
        
        try:
            logger.info(f"Uploading image: {image_path}")
            uploaded_file = self.client.upload_file(file=open(image_path, "rb"), purpose="general")
            
            # Use 'id_' as alias for 'id' if present, or fallback
            if hasattr(uploaded_file, 'id_'):
                return uploaded_file.id_
            elif hasattr(uploaded_file, 'id'):
                return uploaded_file.id
            
            # Fallback to model_dump if attribute access fails
            try:
                return uploaded_file.model_dump().get("id") or uploaded_file.model_dump().get("id_")
            except:
                pass
                
            logger.error(f"Could not find ID in uploaded file object: {dir(uploaded_file)}")
            return None
        except Exception as e:
            logger.error(f"Failed to upload image {image_path}: {e}")
            logger.error(f"Upload failed: {e}")
            return None

    def classify_page(self, image_path: str, document_types: Optional[List[Dict[str, str]]] = None) -> ClassificationResult:
        if not self.client:
            logger.warning("GigaChat client not initialized. Returning mock data.")
            return ClassificationResult(document_type="unknown", confidence=0.0)

        try:
            # 1. Upload Image
            file_id = self._upload_image(image_path)
            if not file_id:
                logger.error("Failed to upload image for classification")
                return ClassificationResult(document_type="error", confidence=0.0)

            # 2. Prepare Prompt
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

            prompt = f"""
{type_instruction}

Верни JSON. Без маркдауна (```json).
{{"document_type": "string", "confidence": 0.0-1.0}}
            """
            
            # 3. Send Message with Attachment
            payload = Chat(
                messages=[
                    Messages(
                        role=MessagesRole.USER,
                        content=prompt,
                        attachments=[file_id] 
                    )
                ],
                temperature=self.temperature,
                max_tokens=200
            )
            
            response = self.client.chat(payload)
            content = response.choices[0].message.content
            raw_response = content
            
            # Clean up potential markdown
            content = content.replace("```json", "").replace("```", "").strip()
            
            data = json.loads(content)
            return ClassificationResult(
                document_type=data.get("document_type", "unknown"),
                confidence=float(data.get("confidence", 0.0)),
                raw_response=raw_response
            )

        except Exception as e:
            logger.error(f"Error classifying page: {e}")
            logger.error(f"Classify exception: {e}")
            return ClassificationResult(document_type="error", confidence=0.0, raw_response=f"Error: {str(e)}")


    def classify_document(self, image_paths: List[str], document_types: Optional[List[Dict[str, str]]] = None) -> ClassificationResult:
        if not image_paths:
             return ClassificationResult(document_type="unknown", confidence=0.0)
        return self.classify_page(image_paths[0], document_types)

    def extract_document(self, images_data: List[Dict[str, Any]], json_schema: Dict[str, Any]) -> ExtractionResult:
        """
        Extracts a document entirely from RAM (bytes), skipping disk IO.
        """
        if not self.client:
            logger.warning("GigaChat client not initialized. Returning mock data.")
            return ExtractionResult(fields={}, stamps=[], signatures=[], raw_response="{}")

        try:
            limited_data = images_data[:10]
            
            all_attachments = []
            filenames = []
            for img in limited_data:
                fid = self._upload_image_bytes(img["bytes"], img["name"])
                if fid:
                    all_attachments.append(fid)
                    filenames.append(img["name"])
            
            if not all_attachments:
                logger.error("No images successfully uploaded for extraction")
                return ExtractionResult(fields={}, stamps=[], signatures=[], raw_response="Error: Upload failed")

            if not json_schema:
                schema_str = "СХЕМА ПУСТАЯ. Извлеки все главные данные документа (тип, номер, дата, покупатель, продавец, суммы, позиции) в виде логичного JSON."
            else:
                schema_str = json.dumps(json_schema, ensure_ascii=False, indent=2)
            
            prompt = f"""
Ты извлекаешь данные из документа по JSON схеме.

ЗАДАЧА:
Перед тобой страницы одного документа: {filenames}.
Твоя задача — извлечь данные из этих страниц и заполнить следующую JSON-схему:
{schema_str}

ПРАВИЛА:
1. Пиши ТОЛЬКО то, что видишь на картинках. Если поля нет - пиши `null`.
2. Верни чистый JSON-объект, строго соответствующий схеме. Обязательно соблюдай структуру иерархии (не прячь ответ внутрь поля structured).
3. ВАЖНО: Если в схеме есть поле `raw_text`, ты ОБЯЗАН вернуть его ПУСТЫМ (""). КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО извлекать весь текст документа (особенно таблицы), иначе система зависнет на 5 минут!
4. Верни ТОЛЬКО JSON-объект. Больше ни единого слова. Без маркдауна (без ```json).
            """

            payload = Chat( 
                messages=[
                    Messages(
                        role=MessagesRole.USER,
                        content=prompt,
                        attachments=all_attachments
                    )
                ],
                temperature=self.temperature,
                max_tokens=8000 # Increased to prevent 'Unterminated string' errors
            )
            
            response = self.client.chat(payload)
            content = response.choices[0].message.content
            raw_response = content
            
            # Clean up JSON
            content = content.replace("```json", "").replace("```", "").strip()
            # In case it still hallucinated an array for one document
            if content.startswith("[") and content.endswith("]"):
                content = content[1:-1].strip()
                
            try:
                data = json.loads(content)
            except Exception as e:
                logger.error(f"GigaChat JSON Decode Error: {e}")
                data = {}
                
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            elif not isinstance(data, dict):
                data = {}
                
            # GigaChat sometimes wraps the entire requested schema inside a "structured" or "fields" root key
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
                 
            # Robust Type Coercion: Prevent Pydantic ValidationError if LLM returns strings instead of objects
            stamps = [s if isinstance(s, dict) else {"value": str(s)} for s in stamps if s is not None]
            signatures = [s if isinstance(s, dict) else {"value": str(s)} for s in signatures if s is not None]

            return ExtractionResult(
                fields=data,
                stamps=stamps,
                signatures=signatures,
                raw_response=raw_response
            )
            
        except Exception as e:
            logger.error(f"GigaChat extraction error: {e}")
            # Try to return the raw_response if it was initialized before crashing
            failed_response = raw_response if 'raw_response' in locals() else f"Error: {e}"
            return ExtractionResult(fields={}, stamps=[], signatures=[], raw_response=failed_response)

    def validate_extraction(self, extraction_result: ExtractionResult, images_data: List[Dict[str, Any]]) -> bool:
        if not self.client:
            return True

        try:
            # 1. Upload First Page (reuse if possible, but for simplicity upload again or cache logic needed)
            # For now, re-upload to be safe and stateless
            file_id = self._upload_image(image_paths[0])
            if not file_id:
                return True

            # 2. Prepare Prompt
            data_str = json.dumps(extraction_result.fields, ensure_ascii=False)
            prompt = f"""
            You are a QA auditor. Verify the extracted data against the document image.
            
            Extracted Data:
            {data_str}
            
            Task:
            1. Check if the extracted values match the visible text in the image.
            2. Check for logical inconsistencies (e.g. totals matching subtotals).
            3. Return JSON:
            {{
                "is_valid": boolean,
                "confidence": float,
                "reason": "string"
            }}
            """
            
            payload = Chat(
                messages=[
                    Messages(
                        role=MessagesRole.USER,
                        content=prompt,
                        attachments=[file_id]
                    )
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            response = self.client.chat(payload)
            content = response.choices[0].message.content
            content = content.replace("```json", "").replace("```", "").strip()
            
            data = json.loads(content)
            return data.get("is_valid", True)

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return True 

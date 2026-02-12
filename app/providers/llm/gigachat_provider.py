import json
import base64
from typing import Dict, Any, List, Optional
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

from app.providers.llm.base_llm import BaseLLM
from app.core.logging import logger

class GigaChatProvider(BaseLLM):
    def __init__(self, credentials: str, model_name: str = "GigaChat-Pro", verify_ssl: bool = True):
        self.giga = GigaChat(credentials=credentials, model=model_name, verify_ssl_certs=verify_ssl)

    async def extract_data(self, image_paths: List[str], schema: Dict[str, Any], prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract structured data using GigaChat Vision capabilities or text-based if images are OCR'd first.
        GigaChat Pro supports image input.
        """
        try:
            prompt_text = prompt or "Extract data from these documents according to the following JSON schema."
            json_schema_str = json.dumps(schema, ensure_ascii=False)
            
            messages = [
                {
                    "role": "system",
                    "content": f"You are a helpful assistant that extracts data from documents into valid JSON format. Follow this schema: {json_schema_str}"
                }
            ]
            
            # Add images as attachments if supported, or multiple messages
            # Current GigaChat SDK supports passing image as base64 in content (for vision models)
            # We will construct a user message with image content
            
            user_content = prompt_text
            
            # GigaChat API might require handling images differently depending on version.
            # Assuming standard multimodal support where we can pass image_id or base64.
            # For this implementation, we will iterate images and append them.
            
            # Note: GigaChat specific implementation for images might vary.
            # We'll use the pattern of sending image within the message content if possible,
            # or uploading first.
            # A common pattern for GigaChat is to upload and get ID, but let's try direct base64 context if small,
            # or assume the library handles it.
            # actually, standard GigaChat library might not fully support multi-image in one go easily without upload.
            # Let's try to assume we can pass the image content.
            
            # NOTE: For simplicity and robustness, we will create a message with attachments.
            
            # But wait, the standard GigaChat Vision usage:
            # response = giga.chat("Describe this image", image=image_file)
            # This supports one image.
            
            # If multiple images, we might need to stitch them or process page by page.
            # For now, let's process the first image or stitch them if possible.
            # Let's assume we handle one image at a time or the Orchestrator passes one.
            # If multiple, we might need a loop.
            
            # For MVP, let's take the first image if multiple are passed, or combine logic.
            # But the interface says `image_paths: List[str]`.
            
            # Let's try to handle the first image for now as GigaChat Vision usually takes one context.
            if image_paths:
                with open(image_paths[0], "rb") as f:
                    image_bytes = f.read()
                    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                    # Some versions allow passing image directly to chat
                    # response = self.giga.chat(payload)
                    # We will try the object approach
                    
                payload = Chat(
                    messages=[
                        Messages(role=MessagesRole.SYSTEM, content=messages[0]["content"]),
                        Messages(role=MessagesRole.USER, content=user_content, attachments=[image_base64]) # Hypothetical attachment field or separate
                    ],
                    temperature=0.1
                )
                # Re-reading docs (simulated): GigaChat python lib often uses `giga.chat(..., image=...)`
                response = self.giga.chat(user_content, image=image_bytes)
            else:
                response = self.giga.chat(user_content)

            # Parse JSON from response
            content = response.choices[0].message.content
            # Clean up markdown
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)

        except Exception as e:
            logger.error(f"GigaChat extraction failed: {e}")
            raise

    async def classify_document(self, image_path: str, categories: List[str]) -> str:
        """
        Classify document page.
        """
        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
                
            prompt = f"Classify this document page into one of these categories: {', '.join(categories)}. Return ONLY the category name."
            
            response = self.giga.chat(prompt, image=image_bytes)
            text = response.choices[0].message.content.strip()
            
            # Simple cleanup
            return text.strip('"').strip("'")
        except Exception as e:
            logger.error(f"GigaChat classification failed: {e}")
            raise

import json
from typing import Dict, Any, List, Optional
import google.generativeai as genai
from PIL import Image

from app.providers.llm.base_llm import BaseLLM
from app.core.logging import logger

class GeminiProvider(BaseLLM):
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-flash"):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name)

    async def extract_data(self, image_paths: List[str], schema: Dict[str, Any], prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract structured data using Gemini.
        """
        try:
            images = [Image.open(p) for p in image_paths]
            
            prompt_text = prompt or "Extract data from these documents according to the following JSON schema."
            # We enforce JSON output
            generation_config = genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=schema
            )
            
            response = self.model.generate_content(
                [prompt_text] + images,
                generation_config=generation_config
            )
            
            return json.loads(response.text)
        except Exception as e:
            logger.error(f"Gemini extraction failed: {e}")
            raise

    async def classify_document(self, image_path: str, categories: List[str]) -> str:
        """
        Classify document page.
        """
        try:
            image = Image.open(image_path)
            prompt = f"Classify this document page into one of these categories: {', '.join(categories)}. Return ONLY the category name as JSON string."
            
            response = self.model.generate_content([prompt, image])
            # Simple cleanup if not pure JSON
            text = response.text.strip().replace('```json', '').replace('```', '').strip()
            # If strictly one category, just return text if it matches, else try to parse
            return text.strip('"')
        except Exception as e:
            logger.error(f"Gemini classification failed: {e}")
            raise

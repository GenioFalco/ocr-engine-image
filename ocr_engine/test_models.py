
import os
import sys
import json
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole

def test_models():
    api_key = os.environ.get("GIGACHAT_CREDENTIALS")
    if not api_key:
        print("ERROR: GIGACHAT_CREDENTIALS not set")
        return

    # Create dummy image
    image_path = "test_image.jpg"
    if not os.path.exists(image_path):
        from PIL import Image
        img = Image.new('RGB', (100, 100), color = 'red')
        img.save(image_path)

    try:
        client = GigaChat(credentials=api_key, verify_ssl_certs=False)
        
        # 1. Upload
        print(f"Uploading {image_path}...")
        uploaded_file = client.upload_file(file=open(image_path, "rb"), purpose="general")
        file_id = getattr(uploaded_file, 'id_', getattr(uploaded_file, 'id', None))
        
        if not file_id:
             # Fallback
             try:
                 file_id = uploaded_file.model_dump().get("id") or uploaded_file.model_dump().get("id_")
             except: pass
        
        if not file_id:
            print(f"ERROR: Could not get file ID from upload response: {uploaded_file}")
            return

        print(f"File uploaded successfully. ID: {file_id}")

        # 2. Test Models
        models_to_test = [
            "GigaChat", 
            "GigaChat-Pro", 
            "GigaChat-Preview", 
            "GigaChat-Plus",
            "GigaChat-2",
            "GigaChat-2-Pro",
            "GigaChat-2-Max"
        ]

        print("\n--- Testing Models ---")
        for model in models_to_test:
            print(f"Testing {model}...", end=" ")
            try:
                payload = Chat(
                    messages=[
                        Messages(
                            role=MessagesRole.USER,
                            content="Describe this image in one word.",
                            attachments=[file_id]
                        )
                    ],
                    model=model,
                    max_tokens=10
                )
                response = client.chat(payload)
                print(f"SUCCESS! Response: {response.choices[0].message.content}")
            except Exception as e:
                print(f"FAILED. Error: {e}")

    except Exception as e:
        print(f"Global Error: {e}")
    finally:
        if os.path.exists(image_path):
            os.remove(image_path)

if __name__ == "__main__":
    test_models()

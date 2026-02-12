import requests
import time
import os

BASE_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")

# 1. Configuration - EDIT THESE
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS", "MDE5YzFkY2MtMWQzYS03OGM3LTgyYmYtN2RlYmU5NTc0ZDgyOmUxMmFmMzAzLWU3MjEtNGM5OS05MTg3LTg3NGQwOWU5Y2JkMA==") # or put actual key

def run_demo():
    print(f"Checking API health at {BASE_URL.replace('/api/v1', '/health')}...")
    try:
        resp = requests.get("http://localhost:8000/health")
        if resp.status_code != 200:
            print("API is not healthy yet. Is docker running?")
            return
    except Exception as e:
        print(f"Could not connect to API: {e}")
        return

    # 2. Register Model
    print("\n--- Registering GigaChat Model ---")
    model_payload = {
        "name": "GigaChat-Pro",
        "provider": "gigachat",
        "api_key": GIGACHAT_CREDENTIALS,
        "parameters": {"temperature": 0.1}
    }
    resp = requests.post(f"{BASE_URL}/models/", json=model_payload)
    if resp.status_code == 201:
        print("Model registered successfully.")
    elif resp.status_code == 400: # Already exists maybe
        print("Model might already exist or invalid request.")
        print(resp.json())
    else:
        print(f"Error registering model: {resp.text}")

    # 3. Create Contract (Example: Act)
    print("\n--- Creating Contract (Act of Acceptance) ---")
    contract_schema = {
        "type": "object",
        "properties": {
            "document_number": {"type": "string"},
            "document_date": {"type": "string"},
            "total_amount": {"type": "number"},
            "performer_inn": {"type": "string"},
            "customer_inn": {"type": "string"}
        },
        "required": ["document_number", "total_amount"]
    }
    
    contract_payload = {
        "name": "Act",
        "description": "Standard act of acceptance",
        "schema": contract_schema
    }
    
    resp = requests.post(f"{BASE_URL}/contracts/", json=contract_payload)
    if resp.status_code == 201:
        print("Contract 'Act' created.")
    elif resp.status_code == 400:
        print("Contract 'Act' already exists.")
    else:
        print(f"Error creating contract: {resp.text}")

    # 4. Upload Document
    # Create a dummy PDF for testing if none exists
    dummy_pdf = "test_document.pdf"
    if not os.path.exists(dummy_pdf):
        print(f"\nCreating dummy PDF '{dummy_pdf}' for testing...")
        try:
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt="Act No. 123 dated 2023-10-25", ln=1, align="C")
            pdf.cell(200, 10, txt="Total Amount: 5000.00", ln=2, align="L")
            pdf.output(dummy_pdf)
        except ImportError:
            print("fpdf not installed, skipping PDF creation. Make sure you have a PDF to test.")
    
    if os.path.exists(dummy_pdf):
        print(f"\n--- Uploading '{dummy_pdf}' ---")
        with open(dummy_pdf, "rb") as f:
            files = {"file": (dummy_pdf, f, "application/pdf")}
            resp = requests.post(f"{BASE_URL}/documents/upload", files=files)
            
        if resp.status_code == 201:
            doc_data = resp.json()
            doc_id = doc_data["id"]
            print(f"Document uploaded. ID: {doc_id}. Status: {doc_data['status']}")
            
            # 5. Poll for results
            print("Waiting for processing...")
            for _ in range(10):
                time.sleep(2)
                status_resp = requests.get(f"{BASE_URL}/documents/{doc_id}")
                status_data = status_resp.json()
                status = status_data["status"]
                print(f"Current status: {status}")
                if status in ["completed", "failed"]:
                    print("\n--- Final Result ---")
                    print(status_data)
                    break
        else:
            print(f"Upload failed: {resp.text}")
    else:
        print(f"Please place a PDF named '{dummy_pdf}' in this folder to test upload.")

if __name__ == "__main__":
    # Ensure requests/fpdf installed
    # pip install requests fpdf
    run_demo()

import requests
import time
import os
import json
import sys

# --- CONFIGURATION ---
API_URL = os.getenv("API_URL", "http://localhost:8000/api/v1")
GIGACHAT_KEY = os.getenv("GIGACHAT_CREDENTIALS", "YOUR_GIGACHAT_KEY_HERE")

# Set these to your actual file paths
DOCUMENT_PATH = "my_document.pdf"  # Replace with your file path
CONTRACT_PATH = "my_contract.json" # Replace with your contract JSON path
# ---------------------

def main():
    print(f"--- OCR Engine Processor ---")
    print(f"API URL: {API_URL}")
    print(f"Document: {DOCUMENT_PATH}")
    print(f"Contract: {CONTRACT_PATH}")

    # 1. Check Files
    if not os.path.exists(DOCUMENT_PATH):
        print(f"[ERROR] Document file not found: {DOCUMENT_PATH}")
        return
    if not os.path.exists(CONTRACT_PATH):
        print(f"[ERROR] Contract file not found: {CONTRACT_PATH}")
        # Create a dummy contract if missing for testing
        with open(CONTRACT_PATH, "w", encoding="utf-8") as f:
            json.dump({
                "name": "Default Contract",
                "description": "Auto-generated contract",
                "schema": {
                    "type": "object",
                    "properties": {"summary": {"type": "string"}},
                    "required": ["summary"]
                }
            }, f, indent=2)
        print(f"[INFO] Created dummy contract at {CONTRACT_PATH}")

    # 2. Check API
    try:
        requests.get(f"{API_URL.replace('/api/v1', '')}/health")
    except Exception:
        print(f"[ERROR] Cannot connect to API at {API_URL}. Is Docker running?")
        return

    # 3. Register Model (Idempotent)
    print("\n[1/4] Ensuring Model is registered...")
    try:
        requests.post(f"{API_URL}/models/", json={
            "name": "GigaChat-Pro",
            "provider": "gigachat",
            "api_key": GIGACHAT_KEY,
            "parameters": {"temperature": 0.1}
        })
    except Exception as e:
        print(f"[WARN] Model registration issue (might already exist): {e}")

    # 4. Create/Update Contract
    print("\n[2/4] Uploading Contract schema...")
    with open(CONTRACT_PATH, "r", encoding="utf-8") as f:
        contract_data = json.load(f)
    
    # Ensure payload matches API expectation
    # API expects: name, description, json_schema (aliased as schema)
    # If user JSON is just the raw JSON-schema, wrap it.
    if "properties" in contract_data or "type" in contract_data:
        # It's a raw JSON schema, wrap it
        payload = {
            "name": os.path.splitext(os.path.basename(CONTRACT_PATH))[0],
            "description": "Imported from file",
            "schema": contract_data # will be mapped to json_schema by alias
        }
    else:
        # Assume it's a full contract object
        payload = contract_data

    resp = requests.post(f"{API_URL}/contracts/", json=payload)
    if resp.status_code not in [200, 201, 400]:
        print(f"[ERROR] Contract creation failed: {resp.text}")
        return
    print("Contract ready.")

    # 5. Upload Document
    print(f"\n[3/4] Uploading Document '{DOCUMENT_PATH}'...")
    with open(DOCUMENT_PATH, "rb") as f:
        # Determine mime type roughly
        mime = "application/pdf" if DOCUMENT_PATH.lower().endswith(".pdf") else "image/jpeg"
        files = {"file": (os.path.basename(DOCUMENT_PATH), f, mime)}
        # We can optionally specify contract_id if we have multiple, 
        # but for now orchestrator takes all active contracts.
        resp = requests.post(f"{API_URL}/documents/upload", files=files)

    if resp.status_code != 201:
        print(f"[ERROR] Upload failed: {resp.text}")
        return

    doc_data = resp.json()
    doc_id = doc_data["id"]
    print(f"Document ID: {doc_id}")

    # 6. Poll for Result
    print("\n[4/4] Processing...")
    while True:
        time.sleep(2)
        status_resp = requests.get(f"{API_URL}/documents/{doc_id}")
        if status_resp.status_code != 200:
            print("Error checking status.")
            break
            
        data = status_resp.json()
        status = data["status"]
        print(f"Status: {status}...", end="\r")

        if status in ["completed", "failed"]:
            print(f"\nFinished with status: {status}")
            
            # Save result
            output_file = f"result_{doc_id}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"\n[SUCCESS] Result saved to: {output_file}")
            break

if __name__ == "__main__":
    main()

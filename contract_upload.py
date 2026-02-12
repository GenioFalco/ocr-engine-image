import requests
import json
import os

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8090/api/v1")
CONTRACT_FILE = "contract.txt"

def main():
    print(f"Read contract from: {CONTRACT_FILE}")
    
    if not os.path.exists(CONTRACT_FILE):
        print(f"Error: File {CONTRACT_FILE} not found!")
        return

    try:
        with open(CONTRACT_FILE, "r", encoding="utf-8") as f:
            schema_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in file. {e}")
        return

    # Payload construction
    payload = {
        "name": "Big Contract", 
        "description": "Large schema imported from file",
        "schema": schema_data
    }

    print(f"Uploading to {API_URL}/contracts/ ...")
    try:
        resp = requests.post(f"{API_URL}/contracts/", json=payload, timeout=30)
        
        if resp.status_code in [200, 201]:
            print("\n[SUCCESS] Contract created!")
            print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
        else:
            print(f"\n[ERROR] Server returned {resp.status_code}")
            print(resp.text)
            
    except requests.exceptions.Timeout:
        print("\n[ERROR] Request timed out. The server is taking too long.")
    except Exception as e:
        print(f"\n[ERROR] Connection failed: {e}")

if __name__ == "__main__":
    main()

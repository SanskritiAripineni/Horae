import requests
import json
import time
import subprocess

# Start the server in the background
server_process = subprocess.Popen(["python3", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"])
time.sleep(3) # Wait for server to start

try:
    url = "http://localhost:8000/api/process_journals"
    
    # Create sample journal payload matching ApiJournalEntry
    payload = {
        "journals": [
            {
                "id": "1",
                "entry_number": 1,
                "created_at": "2024-05-10 10:00:00",
                "period": "Morning sequence",
                "content": "Felt quite anxious today about the upcoming project deadline. Barely slept.",
                "timestamp": "2024-05-10 10:00:00"
            }
        ],
        "user_id": "test_user"
    }
    
    print("Sending test request to API...")
    response = requests.post(url, json=payload)
    
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        print("Response received successfully!")
        data = response.json()
        print(f"Status: {data.get('status')}")
        print(f"Errors: {data.get('errors')}")
        if data.get('mental_health'):
            print(f"Mental Health Risk Level: {data['mental_health'].get('risk_level')}")
    else:
        print(f"Failed: {response.text}")
        
finally:
    # Cleanup
    server_process.terminate()
    server_process.wait()

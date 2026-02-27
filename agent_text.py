import requests
import json

# 1. Configuration
API_URL = "http://127.0.0.1:8000/finance/api/agent/transaction/"
TOKEN = "ba42dd8babe509c7ed11601e130f59f982f74aa6 "

def simulate_ai_agent(user_command):
    print(f"Agent command received: '{user_command}'")
    
    # 2. Simulate parsed result from an LLM.
    mock_llm_data = {
        "amount": "15.00",
        "currency": "GBP",
        "category": "Food",
        "type": "Expense",
        "note": f"Natural Language Input: {user_command}",
        "date": "2026-02-04T12:00:00Z"
    }

    # 3. Send payload to Django API.
    headers = {
        "Authorization": f"Token {TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(API_URL, json=mock_llm_data, headers=headers)
        if response.status_code == 200:
            print("Record created successfully:", response.json())
        else:
            print(f"Create failed, status={response.status_code}, reason={response.text}")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    simulate_ai_agent("I spent 15 pounds on a burger today")

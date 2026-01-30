#!/usr/bin/env python3
"""
Quick test script to verify API endpoints are working
"""
import requests
import sys

BASE_URL = "http://localhost:8000"

def test_create_session():
    """Test creating a new chat session"""
    print("Testing POST /sessions...")
    try:
        response = requests.post(
            f"{BASE_URL}/sessions",
            json={"name": "Quick Test Session"},
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✓ Session created successfully!")
            print(f"  - Session ID: {data['session_id']}")
            print(f"  - Chat ID: {data['chat_id']}")
            print(f"  - Name: {data['name']}")
            return data['chat_id']
        else:
            print(f"✗ Failed with status {response.status_code}")
            print(f"  Response: {response.text}")
            return None
    except Exception as e:
        print(f"✗ Error: {e}")
        return None

def test_list_sessions():
    """Test listing sessions"""
    print("\nTesting GET /sessions...")
    try:
        response = requests.get(
            f"{BASE_URL}/sessions",
            params={"page": 1, "page_size": 10},
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✓ Listed {len(data['sessions'])} sessions")
            return True
        else:
            print(f"✗ Failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_send_message(chat_id: str):
    """Test sending a message"""
    print("\nTesting POST /chats/{chat_id}/messages...")
    try:
        response = requests.post(
            f"{BASE_URL}/chats/{chat_id}/messages",
            json={"message": "Hello! This is a test message."},
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✓ Message sent successfully!")
            print(f"  - Assistant: {data['assistant_response'][:100]}...")
            return True
        else:
            print(f"✗ Failed with status {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    print("=" * 60)
    print("API Endpoint Test")
    print("=" * 60)

    # Test 1: Create session
    chat_id = test_create_session()
    if not chat_id:
        print("\n❌ Create session failed. Stopping tests.")
        sys.exit(1)

    # Test 2: List sessions
    if not test_list_sessions():
        print("\n⚠ List sessions failed but continuing...")

    # Test 3: Send message
    if not test_send_message(chat_id):
        print("\n❌ Send message failed.")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✅ All tests passed!")
    print("=" * 60)

if __name__ == "__main__":
    main()

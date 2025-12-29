#!/usr/bin/env python3
"""
Test script to generate a sample Lottie animation
"""

import requests
import json

def test_generation():
    """Test JSON generation"""

    # Test data
    test_cases = [
        {
            "template": "Glowing Fish Loader",
            "prompt": "hiển thị logo công ty ở thân con cá",
            "conversation_id": "test_fish"
        },
        {
            "template": "Confetti",
            "prompt": "celebration with company colors",
            "conversation_id": "test_confetti"
        }
    ]

    base_url = "http://localhost:8080/v1/lottie/gen"

    for i, test_case in enumerate(test_cases):
        print(f"\n--- Test Case {i+1}: {test_case['template']} ---")

        try:
            response = requests.post(base_url, json=test_case, timeout=10)

            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success! ID: {result['conversation_id']}")
                print(f"   JSON Path: {result['json_path']}")
                print(f"   Download: {result['download_url']}")
                print(f"   Preview: {result['preview_url']}")

                # Test preview
                preview_response = requests.get(result['preview_url'])
                if preview_response.status_code == 200:
                    print(f"✅ Preview works ({len(preview_response.content)} bytes)")
                else:
                    print(f"❌ Preview failed: {preview_response.status_code}")

            else:
                print(f"❌ Failed: {response.status_code}")
                print(f"   Error: {response.text}")

        except Exception as e:
            print(f"❌ Exception: {str(e)}")

if __name__ == "__main__":
    print("🎨 Testing Lottie JSON Generation...")
    print("Make sure the API server is running on http://localhost:8080")

    test_generation()

    print("\n✅ Test completed!")
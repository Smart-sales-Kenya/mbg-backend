# test_pesapal_urls.py
import requests
import json

def test_pesapal_urls():
    consumer_key = "qkio1BGGYAXTu2JOfm7XSXNruoZsrqEW"
    consumer_secret = "osGQ364R49cXKeOYSpaOnT++rHs="
    
    # Test both URL formats
    url_formats = [
        "https://cybqa.pesapal.com/pesapalv3/api/Auth/RequestToken",  # With /pesapalv3
        "https://cybqa.pesapal.com/api/Auth/RequestToken"             # Without /pesapalv3
    ]
    
    data = {
        "consumer_key": consumer_key,
        "consumer_secret": consumer_secret
    }
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    for url in url_formats:
        print(f"\n🧪 Testing URL: {url}")
        try:
            response = requests.post(url, json=data, headers=headers, timeout=30)
            print(f"📡 Status: {response.status_code}")
            print(f"📡 Response: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                if "token" in result:
                    print("✅ SUCCESS! This URL format works!")
                    return url
                else:
                    print("❌ No token in response")
            else:
                print("❌ HTTP error")
                
        except Exception as e:
            print(f"❌ Error: {e}")
    
    return None

if __name__ == "__main__":
    working_url = test_pesapal_urls()
    if working_url:
        print(f"\n🎉 Use this working URL format: {working_url}")
    else:
        print("\n💥 No URL format worked - credentials may be invalid")
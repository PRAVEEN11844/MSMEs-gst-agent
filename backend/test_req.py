import requests

url = "http://127.0.0.1:8000/api/gst/analyze"
files = {'file': ('test.py', open('main.py', 'rb'), 'text/plain')}
try:
    response = requests.post(url, files=files)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
except Exception as e:
    print(f"Error: {e}")

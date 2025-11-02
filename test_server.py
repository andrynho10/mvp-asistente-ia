"""Script simple para probar el servidor FastAPI."""
import sys
import io
import requests
import json

# Configurar UTF-8 para stdout en Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

url = "http://localhost:8000/ask"
data = {
    "question": "¿Cómo solicito vacaciones?"
}

print("Probando endpoint /ask...")
print(f"URL: {url}")
print(f"Request: {json.dumps(data, indent=2)}\n")

try:
    response = requests.post(url, json=data)
    print(f"Status Code: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print("\n✓ SUCCESS!")
        print(f"\nRespuesta: {result['answer'][:200]}...")
        print(f"\nDocumentos fuente encontrados: {len(result.get('source_documents', []))}")
    else:
        print(f"\n✗ ERROR: {response.text}")
except Exception as e:
    print(f"\n✗ ERROR al conectar: {e}")

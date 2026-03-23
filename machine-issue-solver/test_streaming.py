"""
Streaming diagnostic script.
Tests 3 methods to determine if streaming is truly working.
"""
import requests
import json
import sys
import time

API_KEY = "your-api-key"
MODEL_URL = "https://mycompany.com/api/v1/run/session_id"

headers = {
    "Content-Type": "application/json",
    "x-api-key": API_KEY,
    "Accept": "text/event-stream",
}

json_data = {
    "component_inputs": {
        "model-id": {
            "input_value": "who are you?",
            "max_retries": 0,
            "parameters": '{"temperature":0}',
            "stream": True,
            "system_message": "",
        }
    }
}


def test_iter_content():
    """Method 1: iter_content — reads raw bytes as they arrive (best for diagnosing)."""
    print("\n=== Method 1: iter_content (raw chunks) ===")
    start = time.time()

    response = requests.post(
        MODEL_URL, headers=headers, json=json_data, stream=True
    )
    print(f"Status: {response.status_code}")
    print(f"Headers: {dict(response.headers)}\n")

    first_byte_time = None
    chunk_count = 0

    # chunk_size=None means: yield data as it arrives from the socket
    for chunk in response.iter_content(chunk_size=None):
        if chunk:
            now = time.time()
            if first_byte_time is None:
                first_byte_time = now
                print(f"[Time to first byte: {now - start:.3f}s]")

            chunk_count += 1
            elapsed = now - start
            text = chunk.decode("utf-8", errors="replace")
            # Print with timestamp and flush immediately
            print(f"[{elapsed:7.3f}s] chunk #{chunk_count} ({len(chunk)} bytes): {text[:200]}")
            sys.stdout.flush()

    total = time.time() - start
    print(f"\n--- Total: {chunk_count} chunks in {total:.3f}s ---")
    if chunk_count > 1 and first_byte_time:
        print(f"--- Streaming duration (first to last chunk): {time.time() - first_byte_time:.3f}s ---")


def test_iter_lines():
    """Method 2: iter_lines — splits by newline (standard for SSE)."""
    print("\n=== Method 2: iter_lines (SSE) ===")
    start = time.time()

    response = requests.post(
        MODEL_URL, headers=headers, json=json_data, stream=True
    )

    line_count = 0
    for line in response.iter_lines():
        if line:
            now = time.time()
            line_count += 1
            elapsed = now - start
            decoded = line.decode("utf-8", errors="replace")

            print(f"[{elapsed:7.3f}s] line #{line_count}: {decoded[:200]}")
            sys.stdout.flush()

            # Parse SSE data lines
            if decoded.startswith("data:"):
                try:
                    data = json.loads(decoded[5:].strip())
                    # Extract text content if available (adjust keys to your API)
                    text = (
                        data.get("choices", [{}])[0]
                        .get("delta", {})
                        .get("content", "")
                        or data.get("text", "")
                        or data.get("chunk", "")
                        or data.get("token", "")
                    )
                    if text:
                        print(f"         -> token: {text!r}")
                        sys.stdout.flush()
                except json.JSONDecodeError:
                    pass

    total = time.time() - start
    print(f"\n--- Total: {line_count} lines in {total:.3f}s ---")


def test_raw_socket():
    """Method 3: Read raw from urllib3 socket — bypasses all requests buffering."""
    print("\n=== Method 3: Raw socket read (no buffering) ===")
    start = time.time()

    response = requests.post(
        MODEL_URL, headers=headers, json=json_data, stream=True
    )

    chunk_count = 0
    # Access the underlying urllib3 response for minimal buffering
    raw = response.raw
    while True:
        chunk = raw.read(1024)  # read up to 1024 bytes at a time
        if not chunk:
            break
        now = time.time()
        chunk_count += 1
        elapsed = now - start
        text = chunk.decode("utf-8", errors="replace")
        print(f"[{elapsed:7.3f}s] raw #{chunk_count} ({len(chunk)} bytes): {text[:200]}")
        sys.stdout.flush()

    total = time.time() - start
    print(f"\n--- Total: {chunk_count} reads in {total:.3f}s ---")


if __name__ == "__main__":
    method = sys.argv[1] if len(sys.argv) > 1 else "1"

    if method == "1":
        test_iter_content()
    elif method == "2":
        test_iter_lines()
    elif method == "3":
        test_raw_socket()
    else:
        print("Usage: python test_streaming.py [1|2|3]")
        print("  1 = iter_content (raw chunks)")
        print("  2 = iter_lines (SSE)")
        print("  3 = raw socket read")

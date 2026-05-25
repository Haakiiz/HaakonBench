"""
xai.py — Minimal xAI API test. Says "hei" to Grok and prints the response.

Tests three approaches to isolate the issue:
  1. Raw HTTP (no SDK at all) — chat/completions endpoint
  2. Raw HTTP — Responses API endpoint
  3. OpenAI SDK — responses.create (current approach in llm_client.py)
  4. OpenAI SDK — chat.completions.create

Usage:
    python xai.py                         # uses XAI_API_KEY from .env
    python xai.py --key xai-your-key      # pass key directly
    python xai.py --model grok-4.3        # use a specific model
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error

from dotenv import load_dotenv

load_dotenv()


def get_key(override: str | None = None) -> str:
    key = override or os.getenv("XAI_API_KEY")
    if not key:
        print("ERROR: No API key. Set XAI_API_KEY in .env or pass --key")
        sys.exit(1)
    print(f"Key: {key[:6]}...{key[-4:]}  ({len(key)} chars)")
    if not key.startswith("xai-"):
        print(f"  WARNING: xAI keys should start with 'xai-', yours starts with '{key[:4]}'")
    return key


def test_raw_http(api_key: str, model: str):
    """Test 1: Pure stdlib HTTP — no OpenAI SDK involved at all."""
    print(f"\n{'='*50}")
    print("[1] Raw HTTP POST (urllib, no SDK)")
    print("    Endpoint: https://api.x.ai/v1/chat/completions")
    print(f"    Model: {model}")

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Say hello in 5 words"}],
        "max_tokens": 30,
    }).encode()

    req = urllib.request.Request(
        "https://api.x.ai/v1/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            text = data["choices"][0]["message"]["content"]
            print(f"    Response: {text}")
            print("    RESULT: OK")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"    HTTP {e.code}: {body[:300]}")
        print("    RESULT: FAILED")
        return False
    except Exception as e:
        print(f"    {type(e).__name__}: {e}")
        print("    RESULT: FAILED")
        return False


def test_raw_http_responses_api(api_key: str, model: str):
    """Test 2: Raw HTTP to the Responses API endpoint."""
    print(f"\n{'='*50}")
    print("[2] Raw HTTP POST (urllib, Responses API)")
    print("    Endpoint: https://api.x.ai/v1/responses")
    print(f"    Model: {model}")

    payload = json.dumps({
        "model": model,
        "input": [{"role": "user", "content": "Say hello in 5 words"}],
    }).encode()

    req = urllib.request.Request(
        "https://api.x.ai/v1/responses",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            # Try to extract text from the response structure
            text = (
                data.get("output_text")
                or data.get("text", {}).get("value")
                or next(
                    (item.get("content", [{}])[0].get("text")
                     for item in data.get("output", [])
                     if item.get("type") == "message"),
                    None
                )
                or "? (could not parse response)"
            )
            print(f"    Response: {text}")
            print("    RESULT: OK")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        print(f"    HTTP {e.code}: {body[:300]}")
        print("    RESULT: FAILED")
        return False
    except Exception as e:
        print(f"    {type(e).__name__}: {e}")
        print("    RESULT: FAILED")
        return False


def test_openai_responses(api_key: str, model: str):
    """Test 3: OpenAI SDK — responses.create (what llm_client.py uses now)."""
    print(f"\n{'='*50}")
    print("[3] OpenAI SDK — client.responses.create()")
    print(f"    Model: {model}")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        resp = client.responses.create(
            model=model,
            input=[{"role": "user", "content": "Say hello in 5 words"}],
        )
        print(f"    Response: {resp.output_text}")
        print("    RESULT: OK")
        return True
    except Exception as e:
        print(f"    {type(e).__name__}: {e}")
        print("    RESULT: FAILED")
        return False


def test_openai_chat_completions(api_key: str, model: str):
    """Test 4: OpenAI SDK — chat.completions."""
    print(f"\n{'='*50}")
    print("[4] OpenAI SDK — client.chat.completions.create()")
    print(f"    Model: {model}")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say hello in 5 words"}],
            max_tokens=30,
        )
        print(f"    Response: {resp.choices[0].message.content}")
        print("    RESULT: OK")
        return True
    except Exception as e:
        print(f"    {type(e).__name__}: {e}")
        print("    RESULT: FAILED")
        return False


def main():
    parser = argparse.ArgumentParser(description="xAI API diagnostic")
    parser.add_argument("--key",   help="xAI API key")
    parser.add_argument("--model", default="grok-4.3", help="Model to test (default: grok-4.3)")
    args = parser.parse_args()

    api_key = get_key(args.key)
    model = args.model

    r1 = test_raw_http(api_key, model)
    r2 = test_raw_http_responses_api(api_key, model)
    r3 = test_openai_responses(api_key, model)
    r4 = test_openai_chat_completions(api_key, model)

    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    print(f"  [1] Raw HTTP chat/completions:    {'OK' if r1 else 'FAILED'}")
    print(f"  [2] Raw HTTP responses API:       {'OK' if r2 else 'FAILED'}")
    print(f"  [3] OpenAI SDK responses.create:  {'OK' if r3 else 'FAILED'}")
    print(f"  [4] OpenAI SDK chat.completions:  {'OK' if r4 else 'FAILED'}")

    if not any([r1, r2, r3, r4]):
        print("\nAll 4 tests failed — API key is invalid or expired.")
        print("  → Generate a new one at https://console.x.ai")
    elif r3 and r4:
        print(f"\nBoth SDK approaches work for {model}. llm_client.py should be fine.")


if __name__ == "__main__":
    main()

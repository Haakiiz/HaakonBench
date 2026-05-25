"""
grok.py — Simple xAI Grok chat.

Uses grok-4.3 via the Responses API.

Usage:
    python grok.py                          # uses XAI_API_KEY from .env
    python grok.py --key xai-your-key       # pass key directly
    python grok.py --model grok-4.3         # use a specific model
    python grok.py "What is 2+2?"           # one-shot question
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv(override=True)


def get_api_key(override: str | None = None) -> str:
    key = override or os.getenv("XAI_API_KEY")
    if not key:
        print("ERROR: No API key. Set XAI_API_KEY in .env or pass --key xai-...")
        sys.exit(1)
    if not key.startswith("xai-"):
        print(f"WARNING: xAI keys start with 'xai-', yours starts with '{key[:4]}'")
    return key


def chat(api_key: str, model: str, message: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
    response = client.responses.create(
        model=model,
        input=[{"role": "user", "content": message}],
    )
    return response.output_text


def main():
    parser = argparse.ArgumentParser(description="Simple xAI Grok chat")
    parser.add_argument("message", nargs="?", default=None, help="One-shot message")
    parser.add_argument("--key", help="xAI API key (overrides XAI_API_KEY)")
    parser.add_argument("--model", default="grok-4.3",
                        help="Model (default: grok-4.3)")
    args = parser.parse_args()

    api_key = get_api_key(args.key)
    print(f"Model: {args.model}\n")

    if args.message:
        print(f"You: {args.message}")
        reply = chat(api_key, args.model, args.message)
        print(f"Grok: {reply}")
        return

    print("Interactive mode (type 'quit' to exit)\n")
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input or user_input.lower() in ("quit", "exit", "q"):
            break
        reply = chat(api_key, args.model, user_input)
        print(f"Grok: {reply}\n")


if __name__ == "__main__":
    main()

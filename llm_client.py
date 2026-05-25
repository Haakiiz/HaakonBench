"""
llm_client.py — Unified async LLM client
Supports: Anthropic (Claude), OpenAI (GPT), Google (Gemini), xAI (Grok)

Verified against official docs as of May 22, 2026.
"""

import asyncio
import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from tqdm.asyncio import tqdm

load_dotenv()


def load_config(path: str = "config.yaml") -> dict:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"config.yaml not found at '{path}'. "
            "Did you forget to create it? See the llm-setup skill."
        )
    with open(config_path) as f:
        return yaml.safe_load(f)


class LLMClient:
    """
    A unified async client for calling LLM APIs.
    Reads provider, model, and settings from config.yaml — but provider/model
    can be overridden in __init__ so a single process can drive several models
    in parallel (used by haakonbench.py).
    """

    def __init__(
        self,
        config_path: str = "config.yaml",
        provider: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.config = load_config(config_path)
        self.provider = provider or self.config["provider"]
        self.model = model or self.config["model"]
        self.max_tokens = self.config.get("max_tokens", 1024)
        self.temperature = self.config.get("temperature", 0.7)
        self.workers = self.config.get("workers", 5)
        self._client = self._init_client()

    def _init_client(self):
        if self.provider == "anthropic":
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise EnvironmentError("ANTHROPIC_API_KEY not found in .env")
            return anthropic.AsyncAnthropic(api_key=api_key)

        elif self.provider == "openai":
            from openai import AsyncOpenAI
            api_key = os.getenv("CHATGPT_API_KEY")
            if not api_key:
                raise EnvironmentError("CHATGPT_API_KEY not found in .env")
            return AsyncOpenAI(api_key=api_key)

        elif self.provider == "google":
            from google import genai
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise EnvironmentError("GOOGLE_API_KEY not found in .env")
            return genai.Client(api_key=api_key)

        elif self.provider == "xai":
            from openai import AsyncOpenAI
            api_key = os.getenv("XAI_API_KEY")
            if not api_key:
                raise EnvironmentError("XAI_API_KEY not found in .env")
            return AsyncOpenAI(
                api_key=api_key,
                base_url="https://api.x.ai/v1",
            )

        else:
            raise ValueError(
                f"Unknown provider '{self.provider}'. "
                "Choose from: anthropic, openai, google, xai"
            )

    async def call(self, prompt: str, system: Optional[str] = None) -> str:
        if self.provider == "anthropic":
            kwargs = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                kwargs["system"] = system
            response = await self._client.messages.create(**kwargs)
            return response.content[0].text

        elif self.provider == "openai":
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_completion_tokens": self.max_tokens,
            }
            if not self.model.startswith(("gpt-5", "o1", "o3", "o4")):
                kwargs["temperature"] = self.temperature

            response = await self._client.chat.completions.create(**kwargs)
            return response.choices[0].message.content

        elif self.provider == "xai":
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = await self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
            )
            return response.choices[0].message.content

        elif self.provider == "google":
            from google.genai import types
            config = types.GenerateContentConfig(
                max_output_tokens=self.max_tokens,
                temperature=self.temperature,
                system_instruction=system if system else None,
            )
            response = await self._client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            return response.text

    async def batch_call(
        self,
        prompts: list[str],
        system: Optional[str] = None,
        desc: str = "Processing",
    ) -> list[str]:
        semaphore = asyncio.Semaphore(self.workers)

        async def _limited_call(prompt: str) -> str:
            async with semaphore:
                return await self.call(prompt, system=system)

        tasks = [_limited_call(p) for p in prompts]
        results = await tqdm.gather(*tasks, desc=desc, total=len(tasks))
        return list(results)


if __name__ == "__main__":
    async def _test():
        client = LLMClient()
        print(f"Provider : {client.provider}")
        print(f"Model    : {client.model}")
        print(f"Workers  : {client.workers}")
        print("\nRunning single call test...")
        result = await client.call("Say 'Setup successful!' and nothing else.")
        print(f"Response : {result}")

    asyncio.run(_test())

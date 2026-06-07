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

load_dotenv(override=True)


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
        # Reasoning/thinking knob. None = provider default. Every provider that
        # exposes a knob now uses a NAMED effort level (not a numeric budget):
        #   Anthropic Opus/Sonnet → output_config.effort + adaptive thinking
        #                           (low/medium/high/xhigh/max; budget_tokens is
        #                            removed on Opus 4.7/4.8 and 400s)
        #   OpenAI                → reasoning.effort (low/medium/high/xhigh)
        #   Gemini 3              → thinking_level (low/medium/high)
        #   xAI grok-4.3          → reasoning_effort (low/medium/high)
        self.reasoning_effort = self.config.get("reasoning_effort", None)
        # Populated after each call() so callers can read token usage.
        self.last_usage: Optional[dict] = None
        self._client = self._init_client()

    @staticmethod
    def _usage_dict(input_tokens=0, output_tokens=0, reasoning_tokens=0, total_tokens=None) -> dict:
        input_tokens = int(input_tokens or 0)
        output_tokens = int(output_tokens or 0)
        reasoning_tokens = int(reasoning_tokens or 0)
        if total_tokens is None:
            total_tokens = input_tokens + output_tokens
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens,
            "total_tokens": int(total_tokens or 0),
        }

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
        self.last_usage = None
        if self.provider == "anthropic":
            kwargs = {
                "model": self.model,
                "max_tokens": self.max_tokens,
                "messages": [{"role": "user", "content": prompt}],
                # Explicit timeout suppresses the SDK's non-streaming guard, which
                # otherwise raises for max_tokens > ~21k (our 'max' tier is 32k).
                "timeout": 900.0,
            }
            if system:
                kwargs["system"] = system
            if self.reasoning_effort:
                # Opus 4.7/4.8 & Sonnet 4.6: depth is a NAMED effort level in
                # output_config, paired with adaptive thinking. The old numeric
                # thinking.budget_tokens is removed on these models (400s).
                kwargs["output_config"] = {"effort": self.reasoning_effort}
                kwargs["thinking"] = {"type": "adaptive"}
            response = await self._client.messages.create(**kwargs)
            u = getattr(response, "usage", None)
            if u is not None:
                self.last_usage = self._usage_dict(
                    getattr(u, "input_tokens", 0),
                    getattr(u, "output_tokens", 0),
                )
            # With thinking enabled, content[0] is a thinking block — pull text blocks.
            text = "".join(
                b.text for b in response.content if getattr(b, "type", None) == "text"
            )
            return text

        elif self.provider == "openai":
            is_reasoning = self.model.startswith(("gpt-5", "o1", "o3", "o4"))

            if is_reasoning:
                # Responses API: max_output_tokens is a SHARED budget for
                # reasoning tokens + visible output. To leave ~8k for the
                # answer after medium-effort reasoning, floor at 20k.
                # See CLAUDE.md "Reasoning models and token budgets".
                total_token_budget = max(self.max_tokens, 20000)
                kwargs = {
                    "model": self.model,
                    "input": [{"role": "user", "content": prompt}],
                    "max_output_tokens": total_token_budget,
                }
                if system:
                    kwargs["instructions"] = system
                if self.reasoning_effort:
                    kwargs["reasoning"] = {"effort": self.reasoning_effort}
                response = await self._client.responses.create(**kwargs)
                if getattr(response, "status", None) == "incomplete":
                    reason = getattr(
                        getattr(response, "incomplete_details", None),
                        "reason",
                        "unknown",
                    )
                    raise RuntimeError(
                        f"Responses API returned incomplete (reason={reason}). "
                        f"Reasoning consumed the full {total_token_budget}-token "
                        f"budget. Raise max_tokens or pass reasoning={{'effort': 'low'}}."
                    )
                text = response.output_text
                if not text:
                    raise RuntimeError(
                        f"Responses API returned no visible output "
                        f"(status={getattr(response, 'status', '?')}). "
                        f"Output items: {[getattr(i, 'type', '?') for i in getattr(response, 'output', [])]}"
                    )
                u = getattr(response, "usage", None)
                if u is not None:
                    details = getattr(u, "output_tokens_details", None)
                    reasoning = getattr(details, "reasoning_tokens", 0) if details else 0
                    self.last_usage = self._usage_dict(
                        getattr(u, "input_tokens", 0),
                        getattr(u, "output_tokens", 0),
                        reasoning,
                        getattr(u, "total_tokens", None),
                    )
                return text
            else:
                messages = []
                if system:
                    messages.append({"role": "system", "content": system})
                messages.append({"role": "user", "content": prompt})
                response = await self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_completion_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
                u = getattr(response, "usage", None)
                if u is not None:
                    details = getattr(u, "completion_tokens_details", None)
                    reasoning = getattr(details, "reasoning_tokens", 0) if details else 0
                    self.last_usage = self._usage_dict(
                        getattr(u, "prompt_tokens", 0),
                        getattr(u, "completion_tokens", 0),
                        reasoning,
                        getattr(u, "total_tokens", None),
                    )
                return response.choices[0].message.content

        elif self.provider == "xai":
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": self.max_tokens,
            }
            # grok-4.3 accepts reasoning_effort (low/medium/high); older grok-4
            # rejects it. Sent via extra_body so the OpenAI SDK forwards it
            # verbatim to the xAI endpoint without client-side enum validation.
            if self.reasoning_effort:
                kwargs["extra_body"] = {"reasoning_effort": self.reasoning_effort}
            response = await self._client.chat.completions.create(**kwargs)
            u = getattr(response, "usage", None)
            if u is not None:
                details = getattr(u, "completion_tokens_details", None)
                reasoning = getattr(details, "reasoning_tokens", 0) if details else 0
                self.last_usage = self._usage_dict(
                    getattr(u, "prompt_tokens", 0),
                    getattr(u, "completion_tokens", 0),
                    reasoning,
                    getattr(u, "total_tokens", None),
                )
            return response.choices[0].message.content

        elif self.provider == "google":
            from google.genai import types
            # Gemini 2.5+/3.x: max_output_tokens is a SHARED budget for
            # thinking tokens + visible output (thinking is on by default).
            # Floor at 20k for parity with OpenAI reasoning models.
            # See CLAUDE.md "Reasoning models and token budgets".
            total_token_budget = max(self.max_tokens, 20000)
            config_kwargs = dict(
                max_output_tokens=total_token_budget,
                temperature=self.temperature,
                system_instruction=system if system else None,
            )
            # Gemini 3 uses a named thinking_level (low/medium/high), NOT the old
            # numeric thinking_budget — passing a budget to a Gemini 3 model is a
            # hard error. reasoning_effort carries the level (case-insensitive).
            if self.reasoning_effort:
                config_kwargs["thinking_config"] = types.ThinkingConfig(
                    thinking_level=self.reasoning_effort
                )
            config = types.GenerateContentConfig(**config_kwargs)
            response = await self._client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            um = getattr(response, "usage_metadata", None)
            if um is not None:
                self.last_usage = self._usage_dict(
                    getattr(um, "prompt_token_count", 0),
                    getattr(um, "candidates_token_count", 0),
                    getattr(um, "thoughts_token_count", 0),
                    getattr(um, "total_token_count", None),
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

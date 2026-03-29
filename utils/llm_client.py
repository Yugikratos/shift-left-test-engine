"""Claude API client with automatic fallback to rule-based analysis."""

import json
from config.settings import ANTHROPIC_API_KEY, LLM_MODEL, LLM_ENABLED
from utils.logger import get_logger

log = get_logger("llm_client")


class LLMClient:
    """Wrapper for Claude API with graceful fallback."""

    def __init__(self):
        self.enabled = LLM_ENABLED
        self.client = None

        if self.enabled:
            try:
                from anthropic import Anthropic
                self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
                log.info("Claude API client initialized successfully")
            except Exception as e:
                log.warning(f"Failed to initialize Claude API: {e}. Using rule-based fallback.")
                self.enabled = False
        else:
            log.info("No API key found. Using rule-based fallback mode.")

    def analyze(self, prompt: str, system_prompt: str = None) -> str:
        """Send a prompt to Claude and return the response text.

        If API is unavailable, returns None so callers can use fallback logic.
        """
        if not self.enabled or not self.client:
            log.debug("LLM disabled — returning None for fallback")
            return None

        try:
            messages = [{"role": "user", "content": prompt}]

            kwargs = {
                "model": LLM_MODEL,
                "max_tokens": 4096,
                "messages": messages,
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            response = self.client.messages.create(**kwargs)
            result = response.content[0].text
            log.debug(f"LLM response received ({len(result)} chars)")
            return result

        except Exception as e:
            log.error(f"Claude API call failed: {e}")
            return None

    def analyze_json(self, prompt: str, system_prompt: str = None) -> dict | None:
        """Send a prompt and parse the response as JSON.

        Returns None if API is unavailable or parsing fails.
        """
        result = self.analyze(prompt, system_prompt)
        if result is None:
            return None

        try:
            # Strip markdown code fences if present
            cleaned = result.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            log.warning(f"Failed to parse LLM response as JSON: {e}")
            return None

    @property
    def mode(self) -> str:
        """Return current operating mode."""
        return "AI-Powered (Claude)" if self.enabled else "Rule-Based Fallback"


# Singleton instance
llm_client = LLMClient()

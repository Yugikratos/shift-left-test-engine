"""LLM API client with AWS Bedrock support and fallback to rule-based analysis."""

import json
from config.settings import ANTHROPIC_API_KEY, LLM_MODEL, LLM_ENABLED, LLM_PROVIDER
from utils.logger import get_logger

log = get_logger("llm_client")


class LLMClient:
    """Wrapper for LLM APIs (Anthropic/Bedrock) with graceful fallback."""

    def __init__(self):
        self.enabled = LLM_ENABLED
        self.provider = LLM_PROVIDER
        self.client = None

        if self.enabled:
            try:
                if self.provider == "BEDROCK":
                    import boto3
                    self.client = boto3.client("bedrock-runtime", region_name="us-east-1")
                    log.info("AWS Bedrock API client initialized successfully")
                else:
                    from anthropic import Anthropic
                    if not ANTHROPIC_API_KEY:
                        raise ValueError("ANTHROPIC_API_KEY not set")
                    self.client = Anthropic(api_key=ANTHROPIC_API_KEY)
                    log.info("Claude API client initialized successfully")
            except Exception as e:
                log.warning(f"Failed to initialize {self.provider} API: {e}. Using rule-based fallback.")
                self.enabled = False
        else:
            log.info("LLM disabled. Using rule-based fallback mode.")

    def analyze(self, prompt: str, system_prompt: str = None) -> str:
        """Send a prompt to LLM and return the response text."""
        if not self.enabled or not self.client:
            log.debug("LLM disabled — returning None for fallback")
            return None

        try:
            if self.provider == "BEDROCK":
                body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}]
                }
                if system_prompt:
                    body["system"] = system_prompt
                
                response = self.client.invoke_model(
                    modelId="anthropic.claude-3-sonnet-20240229-v1:0",
                    body=json.dumps(body)
                )
                result_json = json.loads(response.get("body").read())
                result = result_json.get("content", [{}])[0].get("text", "")
            else:
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
            log.error(f"{self.provider} API call failed: {e}")
            return None

    def analyze_json(self, prompt: str, system_prompt: str = None) -> dict | None:
        """Send a prompt and parse the response as JSON."""
        result = self.analyze(prompt, system_prompt)
        if result is None:
            return None

        try:
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
        if not self.enabled:
            return "Rule-Based Fallback"
        return f"AI-Powered ({self.provider})"

# Singleton instance
llm_client = LLMClient()

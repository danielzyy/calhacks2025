# asi1client.py
"""
ASI1Client — Python client for Fetch.ai's ASI:One Mini API
https://innovationlab.fetch.ai/resources/docs/asione/asi1-mini-api-reference
"""

import os
import requests
from typing import List, Dict, Optional, Generator
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()


class ASI1ClientError(Exception):
    """Custom exception for ASI:One client errors."""
    pass


class ASI1Client:
    """
    Client for the ASI:One API (model "asi1-mini").
    Provides simple chat completion and streaming interfaces.
    """

    BASE_URL = "https://api.asi1.ai/v1"

    def __init__(self, api_key: Optional[str] = None, model: str = "asi1-mini"):
        """
        Initialize the ASI1 client.

        Args:
            api_key: API key string. If not given, loaded from .env or environment variable ASI1_API_KEY.
            model: Model ID (default: "asi1-mini").
        """
        self.api_key = api_key or os.getenv("ASI1_API_KEY")
        if not self.api_key:
            raise ASI1ClientError(
                "Missing API key. Set ASI1_API_KEY in your environment or .env file."
            )

        self.model = model
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })

    # ------------------------
    # Internal utility methods
    # ------------------------

    def _handle_response(self, resp: requests.Response) -> Dict:
        """Parse and handle HTTP responses."""
        if resp.status_code != 200:
            try:
                error = resp.json()
            except ValueError:
                error = resp.text
            raise ASI1ClientError(f"API request failed [{resp.status_code}]: {error}")
        try:
            return resp.json()
        except ValueError:
            raise ASI1ClientError("Invalid JSON response from server.")

    # ------------------------
    # Core API methods
    # ------------------------

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> Dict:
        """
        Request a chat completion.

        Args:
            messages: List of messages, each with {"role": "user"/"system"/"assistant", "content": "..."}.
            temperature: Sampling temperature (0–2).
            max_tokens: Maximum tokens to generate.
            stream: Whether to use streaming (Server-Sent Events).

        Returns:
            JSON dict response (if stream=False). Otherwise, returns raw response stream object.
        """
        url = f"{self.BASE_URL}/chat/completions"
        payload = {"model": self.model, "messages": messages}
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if stream:
            payload["stream"] = True

        resp = self._session.post(url, json=payload, stream=stream)
        if stream:
            return resp
        return self._handle_response(resp)

    def chat_completion_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> Generator[str, None, None]:
        """
        Stream a chat completion response (yields incremental text).

        Args:
            messages: Message list as in chat_completion().
            temperature: Optional temperature value.
            max_tokens: Optional max token limit.

        Yields:
            Partial response text chunks from the model.
        """
        resp = self.chat_completion(
            messages=messages, temperature=temperature, max_tokens=max_tokens, stream=True
        )

        if resp.status_code != 200:
            raise ASI1ClientError(
                f"Streaming request failed [{resp.status_code}]: {resp.text}"
            )

        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue

            data = line[len("data: "):].strip()
            if data == "[DONE]":
                break

            try:
                obj = requests.utils.json.loads(data)
            except Exception:
                continue

            for choice in obj.get("choices", []):
                delta = choice.get("delta", {})
                content = delta.get("content")
                if content:
                    yield content

    # ------------------------
    # Convenience methods
    # ------------------------

    def simple_chat(self, prompt: str, system_prompt: str = "You are a helpful AI assistant.") -> str:
        """
        Simple one-shot chat wrapper.

        Args:
            prompt: User input.
            system_prompt: Optional system instruction.

        Returns:
            Assistant's text response.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
        result = self.chat_completion(messages=messages)
        try:
            return result["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError):
            raise ASI1ClientError("Unexpected response format from API.")


# ------------------------
# Example usage
# ------------------------
if __name__ == "__main__":
    client = ASI1Client()  # automatically loads API key from .env or environment

    print("=== Basic chat completion ===")
    response = client.simple_chat("Explain decentralized AI in simple terms.")
    print(response)

    print("\n=== Streaming mode ===")
    messages = [
        {"role": "system", "content": "You are a helpful AI assistant."},
        {"role": "user", "content": "List three advantages of multi-agent systems."},
    ]
    for chunk in client.chat_completion_stream(messages):
        print(chunk, end="", flush=True)
    print("\n--- done ---")

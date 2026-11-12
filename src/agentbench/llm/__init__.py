"""LLM layer: one interface (LLMClient), many providers.

GeminiClient is NOT imported here on purpose: importing it needs the optional
Gemini SDK. Use ``from agentbench.llm.gemini import GeminiClient`` when you need it.
"""

from agentbench.llm.base import LLMClient, LLMError, LLMResponse, Message, ToolRequest
from agentbench.llm.fake import FakeLLM

__all__ = ["LLMClient", "LLMError", "LLMResponse", "Message", "ToolRequest", "FakeLLM"]

# ADR 0001: Provider-independent LLM layer, Gemini first

- **Status:** Accepted
- **Date:** 2026-11-10

## Context

The framework must call LLMs, but providers differ in SDKs, pricing and availability.
We want to avoid paid services and be able to switch or compare providers.

## Decision

- All code talks to an abstract `LLMClient` interface, never to a vendor SDK directly.
- Each provider is one implementation in its own module (e.g. `llm/gemini.py`).
- **Google Gemini (free tier)** is the first real provider.
- A `FakeLLM` with scripted responses is used for tests.
- The provider is selected by configuration, not by code changes.

## Consequences

- ➕ Adding Ollama, Groq, etc. means adding one module, without touching the runner.
- ➕ Tests are free, offline and deterministic.
- ➖ The interface only exposes features common to all providers; provider-specific
  extras need care.

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from .config import AgentConfig


def create_llm(config: AgentConfig) -> BaseChatModel:
    """Return an LLM instance for the configured provider."""
    provider = config.model_provider.lower()
    model = config.model_name
    temperature = config.temperature

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model,
            temperature=temperature,
            base_url=config.ollama_base_url,
            think=config.thinking,
        )

    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            raise ImportError("Install Anthropic support: pip install 'portfolioiq[anthropic]'")
        kwargs = {"model": model, "temperature": temperature}
        if config.thinking:
            kwargs["thinking"] = {"type": "enabled", "budget_tokens": 5000}
        return ChatAnthropic(**kwargs)

    if provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
        except ImportError:
            raise ImportError("Install OpenAI support: pip install 'portfolioiq[openai]'")
        return ChatOpenAI(model=model, temperature=temperature)

    if provider == "google":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
        except ImportError:
            raise ImportError("Install Google support: pip install 'portfolioiq[google]'")
        return ChatGoogleGenerativeAI(model=model, temperature=temperature)

    raise ValueError(
        f"Unknown provider '{provider}'. Choose from: ollama, anthropic, openai, google"
    )

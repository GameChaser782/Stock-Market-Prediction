"""Basic smoke tests for financial tools."""
import pytest


def test_stock_lookup_import():
    from portfolioiq.tools.stock_lookup import stock_lookup
    assert stock_lookup is not None


def test_get_fundamentals_import():
    from portfolioiq.tools.get_fundamentals import get_fundamentals
    assert get_fundamentals is not None


def test_calculate_indicators_import():
    from portfolioiq.tools.calculate_indicators import calculate_indicators
    assert calculate_indicators is not None


def test_tool_registry():
    from portfolioiq.tools.registry import ToolRegistry
    ToolRegistry.load_builtins()
    tools = ToolRegistry.all()
    names = [t.name for t in tools]
    assert "stock_lookup" in names
    assert "get_fundamentals" in names
    assert "calculate_indicators" in names
    assert "get_history" in names
    assert "news_search" in names


def test_config_load():
    from portfolioiq.config import load_config
    config = load_config("supervisor", config_dir="agents")
    assert config.name == "supervisor"
    assert len(config.tools) > 0

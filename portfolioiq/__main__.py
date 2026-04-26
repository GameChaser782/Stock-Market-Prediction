from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

load_dotenv()


@click.group()
def cli():
    """PortfolioIQ — Multi-agent financial advisor."""
    pass


@cli.command()
@click.option("--provider", default=None, help="LLM provider: ollama | google | anthropic | openai")
@click.option("--model", default=None, help="Model name")
@click.option("--agent", default="supervisor", help="Agent config to load from agents/")
@click.option("--thread", default=None, help="Thread ID for conversation continuity")
@click.option("--user", default="default", help="User ID for long-term memory")
def chat(provider, model, agent, thread, user):
    """Start an interactive chat session with the financial advisor."""
    _apply_overrides(provider, model)
    from .agent import PortfolioAgent
    import uuid

    piq = PortfolioAgent(agent_name=agent)
    thread_id = thread or str(uuid.uuid4())

    click.echo(f"\n  PortfolioIQ Chat  |  {piq.config.model_provider}/{piq.config.model_name}")
    click.echo("  Type 'exit' or Ctrl+C to quit.\n")

    while True:
        try:
            msg = click.prompt("You", prompt_suffix=" > ")
        except (EOFError, KeyboardInterrupt):
            click.echo("\n  Goodbye!")
            break

        if msg.strip().lower() in ("exit", "quit", "q"):
            click.echo("  Goodbye!")
            break

        try:
            response = piq.chat(msg, thread_id=thread_id, user_id=user)
            click.echo(f"\nPortfolioIQ > {response}\n")
        except Exception as e:
            click.echo(f"\n  Error: {e}\n", err=True)


@cli.command()
@click.option("--host", default="0.0.0.0", help="Server host")
@click.option("--port", default=8000, help="Server port", type=int)
@click.option("--provider", default=None, help="LLM provider")
@click.option("--model", default=None, help="Model name")
@click.option("--agent", default="supervisor", help="Agent config to load")
@click.option("--skip-frontend-build", is_flag=True, help="Skip rebuilding frontend/out before serving")
def serve(host, port, provider, model, agent, skip_frontend_build):
    """Start the PortfolioIQ API server."""
    _apply_overrides(provider, model)
    if not skip_frontend_build:
        _build_frontend_export()
    from .agent import PortfolioAgent
    piq = PortfolioAgent(agent_name=agent)
    piq.serve(host=host, port=port)


@cli.command()
@click.argument("ticker")
@click.option("--provider", default=None, help="LLM provider")
@click.option("--model", default=None, help="Model name")
@click.option("--rounds", default=3, help="Number of debate rounds (1-5)", type=click.IntRange(1, 5))
def debate(ticker, provider, model, rounds):
    """Run a live bull vs bear debate on a stock."""
    _apply_overrides(provider, model)
    from .graphs.debate import run_debate
    from .config import load_config

    click.echo(f"\n  Starting {rounds}-round debate for {ticker.upper()}...")
    click.echo("  Fetching data and building arguments...\n")

    try:
        config = load_config("supervisor")
        result = run_debate(ticker.upper(), rounds=rounds, config=config)

        click.echo(f"{'='*60}")
        click.echo(f"  DEBATE: {ticker.upper()}")
        click.echo(f"{'='*60}\n")

        for i, (bull_arg, bear_arg) in enumerate(zip(result["bull_arguments"], result["bear_arguments"]), 1):
            click.echo(f"--- Round {i} ---")
            click.echo(f"\nBULL:\n{bull_arg}\n")
            click.echo(f"BEAR:\n{bear_arg}\n")

        click.echo(f"{'='*60}")
        click.echo("  MODERATOR VERDICT")
        click.echo(f"{'='*60}\n")

        verdict = result.get("verdict", {})
        if isinstance(verdict, dict):
            click.echo(f"Verdict:         {verdict.get('verdict', 'N/A')}")
            click.echo(f"Confidence:      {verdict.get('confidence', 'N/A')}%")
            click.echo(f"Stronger case:   {verdict.get('stronger_case', 'N/A').upper()}")
            click.echo(f"\nBull summary:    {verdict.get('bull_summary', '')}")
            click.echo(f"\nBear summary:    {verdict.get('bear_summary', '')}")
            click.echo(f"\nKey factors:")
            for f in verdict.get("key_factors", []):
                click.echo(f"  • {f}")
            click.echo(f"\nRecommendation: {verdict.get('recommendation', '')}")
            click.echo(f"\n{verdict.get('disclaimer', '')}\n")
        else:
            click.echo(str(verdict))

    except Exception as e:
        click.echo(f"\n  Error: {e}\n", err=True)
        sys.exit(1)


@cli.command()
@click.option("--ticker", required=True, help="Stock ticker to train on (e.g. AAPL)")
@click.option("--days", default=730, help="Days of historical data to use", type=int)
def train(ticker, days):
    """Train ML price direction model on historical stock data."""
    try:
        from .ml.train import train as ml_train
        result = ml_train(ticker.upper(), days=days)
        click.echo(f"\n  Training complete for {ticker.upper()}")
        click.echo(f"  Samples:     {result['samples']}")
        click.echo(f"  CV Accuracy: {result['accuracy_cv']:.2%}")
        click.echo(f"  Top features: {', '.join(k for k, _ in result['top_features'][:3])}")
        click.echo(f"\n  Run `portfolioiq predict --ticker {ticker.upper()}` for a prediction.\n")
    except ImportError:
        click.echo("\n  Install ML deps first: pip install 'portfolioiq[ml]'\n", err=True)
    except Exception as e:
        click.echo(f"\n  Error: {e}\n", err=True)


@cli.command()
@click.option("--ticker", required=True, help="Stock ticker to predict")
def predict(ticker):
    """Predict 5-day price direction using trained ML model."""
    try:
        from .ml.predict import predict as ml_predict
        r = ml_predict(ticker.upper())
        if "error" in r:
            click.echo(f"\n  {r['error']}\n")
            return
        click.echo(f"\n  ML Prediction: {ticker.upper()}")
        click.echo(f"  Current Price: {r.get('current_price', 'N/A')}")
        click.echo(f"  Direction:     {r['direction']} (5 trading days)")
        click.echo(f"  Confidence:    {r['confidence']}")
        click.echo(f"  Probability:   {r['probability']:.2%}")
        click.echo(f"\n  {r['disclaimer']}\n")
    except ImportError:
        click.echo("\n  Install ML deps first: pip install 'portfolioiq[ml]'\n", err=True)
    except Exception as e:
        click.echo(f"\n  Error: {e}\n", err=True)


@cli.command()
def setup():
    """Interactive setup wizard: configure your LLM provider and API keys."""
    click.echo("\n  PortfolioIQ Setup\n")

    provider = click.prompt(
        "  Choose your LLM provider",
        type=click.Choice(["ollama", "google", "anthropic", "openai"], case_sensitive=False),
    )

    model_defaults = {
        "ollama": "qwen3.5",
        "google": "gemini-2.5-flash",
        "anthropic": "claude-sonnet-4-20250514",
        "openai": "gpt-4o",
    }
    default_model = model_defaults[provider]
    model = click.prompt(f"  Model name", default=default_model)

    env_lines = [f"AGENT_PROVIDER={provider}", f"AGENT_MODEL={model}"]

    if provider != "ollama":
        key_names = {
            "google": "GOOGLE_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "openai": "OPENAI_API_KEY",
        }
        key_name = key_names[provider]
        api_key = click.prompt(f"  {key_name}", hide_input=True)
        env_lines.append(f"{key_name}={api_key}")

    tavily = click.confirm("\n  Add Tavily API key for better news search? (optional)", default=False)
    if tavily:
        tavily_key = click.prompt("  TAVILY_API_KEY", hide_input=True)
        env_lines.append(f"TAVILY_API_KEY={tavily_key}")

    env_path = ".env"
    with open(env_path, "w") as f:
        f.write("\n".join(env_lines) + "\n")

    click.echo(f"\n  Setup complete! Config saved to {env_path}")
    click.echo("  Run `portfolioiq serve` to start the server.")
    click.echo("  Run `portfolioiq chat` to chat in the terminal.\n")


def _apply_overrides(provider: str | None, model: str | None) -> None:
    if provider:
        os.environ["AGENT_PROVIDER"] = provider
    if model:
        os.environ["AGENT_MODEL"] = model


def _build_frontend_export() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    frontend_dir = repo_root / "frontend"

    if not frontend_dir.exists():
        click.echo("  Frontend directory not found, skipping frontend build.")
        return

    click.echo("\n  Building frontend export...")
    cmd = ["npx", "next", "build", "--webpack"]
    try:
        subprocess.run(cmd, cwd=frontend_dir, check=True)
        click.echo("  Frontend build complete.\n")
    except FileNotFoundError as exc:
        raise click.ClickException(
            "Could not run frontend build. Make sure Node.js and npx are installed."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise click.ClickException(
            f"Frontend build failed with exit code {exc.returncode}. "
            "Fix the frontend build, or rerun with --skip-frontend-build."
        ) from exc


if __name__ == "__main__":
    cli()

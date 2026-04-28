"""Typer CLI client.

The CLI is a thin HTTP client over the FastAPI service. This keeps a single
execution path: every run, whether triggered from the terminal or from a
remote client, goes through the API and the same background worker.

Usage examples:

    python -m cli.cli submit tasks/notepad_example.json
    python -m cli.cli status <task_id>
    python -m cli.cli list
    python -m cli.cli watch <task_id>
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Optional

import httpx
import typer

from app.core.config import settings

app = typer.Typer(help="Windows Desktop Automation Framework CLI")


def _client() -> httpx.Client:
    return httpx.Client(base_url=settings.api_base_url, timeout=10.0)


@app.command()
def submit(
    config: Path = typer.Argument(..., exists=True, readable=True, help="Path to a task JSON file."),
    name: Optional[str] = typer.Option(None, help="Override the 'name' field in the JSON."),
) -> None:
    """Submit a task JSON file to the running API."""
    payload = json.loads(config.read_text(encoding="utf-8"))
    if name:
        payload["name"] = name
    with _client() as http:
        resp = http.post("/run-task", json=payload)
    if resp.status_code >= 400:
        typer.secho(f"error {resp.status_code}: {resp.text}", fg=typer.colors.RED)
        sys.exit(1)
    body = resp.json()
    typer.secho(f"submitted: task_id={body['task_id']} status={body['status']}", fg=typer.colors.GREEN)


@app.command()
def status(task_id: str) -> None:
    """Print the current status (and per-step audit) of a task."""
    with _client() as http:
        resp = http.get(f"/status/{task_id}")
    if resp.status_code >= 400:
        typer.secho(f"error {resp.status_code}: {resp.text}", fg=typer.colors.RED)
        sys.exit(1)
    typer.echo(json.dumps(resp.json(), indent=2, default=str))


@app.command("list")
def list_tasks(limit: int = typer.Option(20, help="Max rows to show.")) -> None:
    """List recent tasks."""
    with _client() as http:
        resp = http.get("/tasks", params={"limit": limit})
    rows = resp.json()
    if not rows:
        typer.echo("(no tasks yet)")
        return
    typer.echo(f"{'task_id':36}  {'status':10}  name")
    typer.echo("-" * 80)
    for r in rows:
        typer.echo(f"{r['id']:36}  {r['status']:10}  {r['name']}")


@app.command()
def cancel(task_id: str) -> None:
    """Cancel a queued task. Running tasks cannot be interrupted."""
    with _client() as http:
        resp = http.post(f"/cancel/{task_id}")
    if resp.status_code >= 400:
        typer.secho(f"error {resp.status_code}: {resp.text}", fg=typer.colors.RED)
        sys.exit(1)
    body = resp.json()
    color = typer.colors.GREEN if body.get("cancelled") else typer.colors.YELLOW
    typer.secho(f"{body['status']}: {body['message']}", fg=color)


@app.command()
def stats() -> None:
    """Show aggregate stats from the running API."""
    with _client() as http:
        resp = http.get("/stats")
    if resp.status_code >= 400:
        typer.secho(f"error {resp.status_code}: {resp.text}", fg=typer.colors.RED)
        sys.exit(1)
    typer.echo(json.dumps(resp.json(), indent=2, default=str))


@app.command()
def health() -> None:
    """Probe the API /health endpoint."""
    with _client() as http:
        try:
            resp = http.get("/health")
        except httpx.HTTPError as exc:
            typer.secho(f"unreachable: {exc}", fg=typer.colors.RED)
            sys.exit(1)
    typer.echo(json.dumps(resp.json(), indent=2, default=str))


@app.command()
def watch(
    task_id: str,
    interval: float = typer.Option(1.0, help="Seconds between polls."),
    timeout: float = typer.Option(300.0, help="Stop polling after this many seconds."),
) -> None:
    """Poll a task until it reaches a terminal state (or timeout)."""
    deadline = time.monotonic() + timeout
    last_status: Optional[str] = None
    with _client() as http:
        while time.monotonic() < deadline:
            resp = http.get(f"/status/{task_id}")
            if resp.status_code >= 400:
                typer.secho(f"error {resp.status_code}: {resp.text}", fg=typer.colors.RED)
                sys.exit(1)
            data = resp.json()
            if data["status"] != last_status:
                typer.echo(f"[{data['status']}] steps={len(data['steps'])} error={data.get('error')}")
                last_status = data["status"]
            if data["status"] in {"success", "failed", "cancelled"}:
                typer.echo(json.dumps(data, indent=2, default=str))
                return
            time.sleep(interval)
    typer.secho("watch timed out", fg=typer.colors.YELLOW)
    sys.exit(2)


if __name__ == "__main__":
    app()

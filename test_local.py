# test_local.py
# Runs a complete research job directly from the terminal.
# No server needed — use this constantly during development.
# It's faster to test this way than starting the full API.
#
# Usage:
#   python test_local.py
#   python test_local.py "What is the history of the internet?"

import asyncio
import sys
from rich.console import Console
from rich.panel import Panel
from config import get_settings
from agents.supervisor import SupervisorAgent
from agents.memory import MemoryManager

console = Console()
settings = get_settings()
memory = MemoryManager()


async def main():
    # Use argument from command line, or fall back to a default query
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = "What are the main differences between supervised and unsupervised machine learning?"

    console.print(Panel(f"[bold]Research Query[/bold]\n{query}", style="blue"))
    console.print(f"[dim]Provider: {settings.llm_provider} | "
                  f"Supervisor: {settings.supervisor_model} | "
                  f"Worker: {settings.worker_model}[/dim]\n")

    supervisor = SupervisorAgent()

    # Start the research job
    job_id = await supervisor.run_research(query)
    console.print(f"Job ID: [bold]{job_id}[/bold]\n")

    # Poll every 2 seconds until finished
    while True:
        await asyncio.sleep(2)
        state = await memory.load(job_id)
        if not state:
            break

        console.print(
            f"[dim]Status: [bold]{state.status}[/bold] | "
            f"Workers done: {len(state.worker_results)}[/dim]"
        )

        if state.status in ("done", "failed"):
            break

    # Show the result
    state = await memory.load(job_id)

    if state.status == "failed":
        console.print(f"\n[red bold]Research failed:[/red bold] {state.error}")
        return

    console.print("\n")
    console.print(Panel(
        state.final_report,
        title=f"[green bold]Research Report — Job {job_id}[/green bold]"
    ))

    # Save report to file
    out_path = f"reports/report_{job_id}.txt"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"Query: {query}\n\n")
        f.write(state.final_report)

    console.print(f"\n[dim]Report saved to {out_path}[/dim]")


if __name__ == "__main__":
    asyncio.run(main())
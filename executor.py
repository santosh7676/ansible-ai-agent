import subprocess
import time
from rich.console import Console
from rich.syntax import Syntax
import socket

console = Console()

def run_command(command: str, stream: bool = True) -> tuple[int, str]:
    """
    Run a shell command and optionally stream output live.
    Returns (exit_code, full_output)
    """
    full_output = []

    process = subprocess.Popen(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    if stream:
        for line in process.stdout:
            line = line.rstrip()
            if line:
                full_output.append(line)
                if "ok:" in line.lower():
                    console.print(f"  [green]✔ {line}[/green]")
                elif "changed:" in line.lower():
                    console.print(f"  [yellow]↺ {line}[/yellow]")
                elif "failed:" in line.lower() or "error" in line.lower():
                    console.print(f"  [red]✘ {line}[/red]")
                elif "skipping:" in line.lower():
                    console.print(f"  [dim]⊘ {line}[/dim]")
                elif "TASK [" in line:
                    console.print(f"\n  [bold white]{line}[/bold white]")
                elif "PLAY [" in line:
                    console.print(f"\n[bold cyan]{line}[/bold cyan]")
                elif "PLAY RECAP" in line:
                    console.print(f"\n[bold cyan]{line}[/bold cyan]")
                elif "RUNNING HANDLER" in line:
                    console.print(f"  [magenta]⚡ {line}[/magenta]")
                elif "WARNING" in line or "DEPRECATION" in line:
                    pass  # Suppress warnings for clean demo output
                else:
                    console.print(f"  [dim]{line}[/dim]")
    else:
        output, _ = process.communicate()
        full_output = output.splitlines()

    process.wait()
    return process.returncode, "\n".join(full_output)


def wait_for_ssh(host: str = "127.0.0.1", port: int = 2222, retries: int = 10) -> bool:
    """
    Wait for SSH to be ready on the container.
    """
    for i in range(retries):
        try:
            sock = socket.create_connection((host, port), timeout=2)
            sock.close()
            return True
        except (socket.error, ConnectionRefusedError):
            import time
            time.sleep(3)
    return False

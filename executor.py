import subprocess
import sys
from rich.console import Console

console = Console()

def run_command(command: str, stream: bool = True) -> tuple[int, str]:
    """
    Run a shell command and optionally stream output live.
    Returns (exit_code, full_output)
    """
    console.print(f"\n[bold cyan]Running:[/bold cyan] {command}\n")
    
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
                # Color code Ansible output
                if "ok:" in line.lower():
                    console.print(f"[green]{line}[/green]")
                elif "changed:" in line.lower():
                    console.print(f"[yellow]{line}[/yellow]")
                elif "failed:" in line.lower() or "error" in line.lower():
                    console.print(f"[red]{line}[/red]")
                elif "skipping:" in line.lower():
                    console.print(f"[dim]{line}[/dim]")
                else:
                    console.print(line)
    else:
        output, _ = process.communicate()
        full_output = output.splitlines()
    
    process.wait()
    return process.returncode, "\n".join(full_output)


def wait_for_ssh(host: str = "127.0.0.1", port: int = 2222, retries: int = 10) -> bool:
    """
    Wait for SSH to be ready on the container.
    """
    import time
    import socket
    
    console.print(f"\n[bold yellow]Waiting for SSH to be ready...[/bold yellow]")
    
    for i in range(retries):
        try:
            sock = socket.create_connection((host, port), timeout=2)
            sock.close()
            console.print(f"[green]SSH is ready![/green]")
            return True
        except (socket.error, ConnectionRefusedError):
            console.print(f"[dim]Attempt {i+1}/{retries} - SSH not ready yet...[/dim]")
            time.sleep(3)
    
    console.print(f"[red]SSH did not become ready in time.[/red]")
    return False

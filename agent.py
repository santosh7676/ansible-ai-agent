import os
import sys
import socket
import time
import requests
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from dotenv import load_dotenv
from prompt_template import generate_playbook_prompt, generate_server_count_prompt
from executor import run_command, wait_for_ssh

load_dotenv()

console = Console()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324")
PLAYBOOK_PATH = "output/playbook.yml"
INVENTORY_PATH = "inventory.ini"

SSH_PORT_START = 2222
SSH_PORT_END = 2230
HTTP_PORT_START = 8080
HTTP_PORT_END = 8090


def step_header(number: int, title: str, start_time: float) -> float:
    """Print a clean step header and return new start time."""
    elapsed = time.time() - start_time
    console.print()
    console.print(Rule(
        f"[bold cyan]Step {number}: {title}[/bold cyan]",
        style="cyan"
    ))
    return time.time()


def step_done(start_time: float) -> None:
    """Print step completion time."""
    elapsed = time.time() - start_time
    console.print(f"  [dim]✓ Done in {elapsed:.1f}s[/dim]")


def call_openrouter(prompt: str) -> str:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}]
    }
    response = requests.post(OPENROUTER_URL, headers=headers, json=payload)
    if response.status_code != 200:
        console.print(f"[red]OpenRouter API error: {response.status_code}[/red]")
        sys.exit(1)
    return response.json()["choices"][0]["message"]["content"].strip()


def get_server_count(user_input: str) -> int:
    prompt = generate_server_count_prompt(user_input)
    result = call_openrouter(prompt)
    try:
        count = int(result.strip())
        return max(1, min(count, SSH_PORT_END - SSH_PORT_START + 1))
    except ValueError:
        return 1


def get_available_ports(start: int, end: int, count: int) -> list:
    available = []
    for port in range(start, end + 1):
        if len(available) == count:
            break
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        if result != 0:
            available.append(port)
    if len(available) < count:
        console.print(f"[red]Not enough available ports in range {start}-{end}[/red]")
        sys.exit(1)
    return available


def remove_existing_containers() -> None:
    console.print("  [dim]Removing existing containers...[/dim]")
    for i in range(1, SSH_PORT_END - SSH_PORT_START + 2):
        run_command(
            f"docker rm -f ansible-target-{i} 2>/dev/null || true",
            stream=False
        )

    # Clean only our port range entries from known_hosts
    console.print(f"  [dim]Cleaning SSH known hosts for port range {SSH_PORT_START}-{SSH_PORT_END}...[/dim]")
    for port in range(SSH_PORT_START, SSH_PORT_END + 1):
        run_command(
            f"ssh-keygen -R '[127.0.0.1]:{port}' 2>/dev/null || true",
            stream=False
        )
    console.print("  [green]Clean slate ready[/green]")

def provision_containers(count: int, ssh_ports: list, http_ports: list) -> list:
    containers = []
    for i, (ssh_port, http_port) in enumerate(zip(ssh_ports, http_ports), start=1):
        name = f"ansible-target-{i}"
        cmd = f"docker run -d --name {name} -p {ssh_port}:22 -p {http_port}:80 ansible-target"
        console.print(f"  [cyan]Provisioning {name} — SSH:{ssh_port} HTTP:{http_port}[/cyan]")
        exit_code, output = run_command(cmd, stream=False)
        if exit_code != 0:
            console.print(f"  [red]Failed to provision {name}[/red]")
            sys.exit(1)
        console.print(f"  [green]✔ {name} is up[/green]")
        containers.append((name, ssh_port, http_port))
    return containers


def generate_inventory(containers: list) -> None:
    lines = ["[webservers]"]
    for name, ssh_port, http_port in containers:
        lines.append(
            f"{name} ansible_host=127.0.0.1 ansible_port={ssh_port} "
            f"ansible_user=ansible ansible_password=ansible "
            f"ansible_ssh_extra_args='-o StrictHostKeyChecking=no'"
        )
    with open(INVENTORY_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Container")
    table.add_column("SSH Port")
    table.add_column("HTTP Port")
    for name, ssh_port, http_port in containers:
        table.add_row(name, str(ssh_port), str(http_port))
    console.print(table)


def save_playbook(content: str) -> None:
    os.makedirs("output", exist_ok=True)
    with open(PLAYBOOK_PATH, "w") as f:
        f.write(content)


def display_playbook(content: str) -> None:
    syntax = Syntax(content, "yaml", theme="monokai", line_numbers=True)
    console.print(syntax)


def verify_services(containers: list) -> None:
    console.print()
    console.print(Rule("[bold green]Verification[/bold green]", style="green"))
    all_ok = True
    for name, ssh_port, http_port in containers:
        exit_code, output = run_command(
            f"docker exec {name} curl -s -o /dev/null -w '%{{http_code}}' http://localhost:80",
            stream=False
        )
        if "200" in output:
            console.print(f"  [green]✔ {name} → HTTP 200  →  curl http://127.0.0.1:{http_port}[/green]")
        else:
            console.print(f"  [yellow]⚠ {name} → not responding yet[/yellow]")
            all_ok = False
    return all_ok


def main():
    total_start = time.time()

    console.print()
    console.print(Panel.fit(
        "[bold green]Ansible AI Agent[/bold green]\n"
        "[dim]From Prompt to Production[/dim]\n"
        f"[dim]Model: {MODEL}[/dim]",
        border_style="green"
    ))

    console.print("\n[bold white]Enter your infrastructure task:[/bold white]")
    user_input = input("  > ").strip()

    if not user_input:
        console.print("[red]No input provided. Exiting.[/red]")
        sys.exit(1)

    # Step 1 - Detect server count
    t = step_header(1, "Detecting target servers", total_start)
    server_count = get_server_count(user_input)
    console.print(f"  [green]✔ Target servers: {server_count}[/green]")
    step_done(t)

    # Step 2 - Get available ports
    t = step_header(2, "Selecting available ports", total_start)
    ssh_ports = get_available_ports(SSH_PORT_START, SSH_PORT_END, server_count)
    http_ports = get_available_ports(HTTP_PORT_START, HTTP_PORT_END, server_count)
    console.print(f"  [green]✔ SSH ports  : {ssh_ports}[/green]")
    console.print(f"  [green]✔ HTTP ports : {http_ports}[/green]")
    step_done(t)

    # Step 3 - Clean up
    t = step_header(3, "Cleaning up existing containers", total_start)
    remove_existing_containers()
    step_done(t)

    # Step 4 - Provision containers
    t = step_header(4, f"Provisioning {server_count} container(s)", total_start)
    containers = provision_containers(server_count, ssh_ports, http_ports)
    step_done(t)

    # Step 5 - Wait for SSH
    t = step_header(5, "Waiting for SSH on all containers", total_start)
    for name, ssh_port, http_port in containers:
        console.print(f"  [dim]Waiting for SSH on {name} (port {ssh_port})...[/dim]")
        if not wait_for_ssh(host="127.0.0.1", port=ssh_port):
            console.print(f"  [red]SSH not ready on {name}. Exiting.[/red]")
            sys.exit(1)
        console.print(f"  [green]✔ {name} SSH ready[/green]")
    step_done(t)

    # Step 6 - Generate inventory
    t = step_header(6, "Generating dynamic inventory", total_start)
    generate_inventory(containers)
    step_done(t)

    # Step 7 - Generate playbook
    t = step_header(7, "Generating Ansible playbook via AI", total_start)
    playbook_content = call_openrouter(generate_playbook_prompt(user_input))
    save_playbook(playbook_content)
    console.print()
    display_playbook(playbook_content)
    step_done(t)

    # Step 8 - Execute playbook
    t = step_header(8, "Executing playbook against all containers", total_start)
    ansible_command = (
        f"ANSIBLE_DEPRECATION_WARNINGS=False "
        f"ANSIBLE_INTERPRETER_PYTHON_FALLBACK=silent "
        f"ansible-playbook -i {INVENTORY_PATH} {PLAYBOOK_PATH} "
        f"--ssh-extra-args='-o StrictHostKeyChecking=no'"
    )
    exit_code, output = run_command(ansible_command)
    step_done(t)

    # Final result
    total_elapsed = time.time() - total_start
    console.print()

    if exit_code == 0:
        verify_services(containers)
        console.print()
        console.print(Panel.fit(
            f"[bold green]SUCCESS[/bold green]\n"
            f"All {server_count} server(s) provisioned and configured!\n"
            f"[dim]Total time: {total_elapsed:.1f}s[/dim]",
            border_style="green"
        ))
        console.print()
        console.print("[bold white]Access your servers:[/bold white]")
        for name, ssh_port, http_port in containers:
            console.print(f"  [cyan]curl http://127.0.0.1:{http_port}[/cyan]  ← {name}")
    else:
        console.print(Panel.fit(
            f"[bold red]FAILED[/bold red]\n"
            "Check the logs above for details.\n"
            f"[dim]Total time: {total_elapsed:.1f}s[/dim]",
            border_style="red"
        ))

if __name__ == "__main__":
    main()

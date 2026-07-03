import os
import sys
import socket
import time
import requests
from rich.console import Console
from rich.panel import Panel
from rich import print as rprint
from dotenv import load_dotenv
from prompt_template import generate_playbook_prompt, generate_server_count_prompt
from executor import run_command, wait_for_ssh

# Load environment variables
load_dotenv()

console = Console()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat-v3-0324")
PLAYBOOK_PATH = "output/playbook.yml"
INVENTORY_PATH = "inventory.ini"

# Port ranges
SSH_PORT_START = 2222
SSH_PORT_END = 2230
HTTP_PORT_START = 8080
HTTP_PORT_END = 8090


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
        console.print(f"[red]OpenRouter API error: {response.status_code} - {response.text}[/red]")
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
    for i in range(1, SSH_PORT_END - SSH_PORT_START + 2):
        run_command(f"docker rm -f ansible-target-{i} 2>/dev/null || true", stream=False)


def provision_containers(count: int, ssh_ports: list, http_ports: list) -> list:
    """
    Spin up fresh containers with SSH and HTTP ports exposed.
    Returns list of (container_name, ssh_port, http_port) tuples.
    """
    containers = []
    for i, (ssh_port, http_port) in enumerate(zip(ssh_ports, http_ports), start=1):
        name = f"ansible-target-{i}"
        cmd = f"docker run -d --name {name} -p {ssh_port}:22 -p {http_port}:80 ansible-target"
        console.print(f"\n[bold cyan]Provisioning container {i}/{count}: {name} (SSH:{ssh_port}, HTTP:{http_port})[/bold cyan]")
        exit_code, output = run_command(cmd)
        if exit_code != 0:
            console.print(f"[red]Failed to provision {name}[/red]")
            sys.exit(1)
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

    console.print(f"\n[green]Inventory generated with {len(containers)} host(s):[/green]")
    for name, ssh_port, http_port in containers:
        console.print(f"  [dim]{name} → SSH:{ssh_port} HTTP:{http_port}[/dim]")


def save_playbook(content: str) -> None:
    os.makedirs("output", exist_ok=True)
    with open(PLAYBOOK_PATH, "w") as f:
        f.write(content)


def verify_services(containers: list) -> None:
    console.print("\n[bold cyan]Verifying services on all containers...[/bold cyan]")
    for name, ssh_port, http_port in containers:
        # Verify via docker exec (internal port 80)
        exit_code, output = run_command(
            f"docker exec {name} curl -s -o /dev/null -w '%{{http_code}}' http://localhost:80",
            stream=False
        )
        if "200" in output:
            console.print(f"[green]{name} → HTTP 200 ✅  (curl http://127.0.0.1:{http_port} from host)[/green]")
        else:
            console.print(f"[yellow]{name} → service not responding yet ⚠️[/yellow]")


def main():
    console.print(Panel.fit(
        "[bold green]Ansible AI Agent[/bold green]\n"
        "[dim]From Prompt to Production[/dim]",
        border_style="green"
    ))

    # Step 1 - Get user input
    console.print("\n[bold white]Enter your infrastructure task:[/bold white]")
    user_input = input("> ").strip()

    if not user_input:
        console.print("[red]No input provided. Exiting.[/red]")
        sys.exit(1)

    # Step 2 - Parse server count
    console.print("\n[bold cyan]Step 1: Detecting number of target servers...[/bold cyan]")
    server_count = get_server_count(user_input)
    console.print(f"[green]Target servers detected: {server_count}[/green]")

    # Step 3 - Get available ports
    console.print(f"\n[bold cyan]Step 2: Finding available ports...[/bold cyan]")
    ssh_ports = get_available_ports(SSH_PORT_START, SSH_PORT_END, server_count)
    http_ports = get_available_ports(HTTP_PORT_START, HTTP_PORT_END, server_count)
    console.print(f"[green]SSH ports  : {ssh_ports}[/green]")
    console.print(f"[green]HTTP ports : {http_ports}[/green]")

    # Step 4 - Remove existing containers
    console.print("\n[bold cyan]Step 3: Cleaning up existing containers...[/bold cyan]")
    remove_existing_containers()

    # Step 5 - Provision containers
    console.print(f"\n[bold cyan]Step 4: Provisioning {server_count} fresh container(s)...[/bold cyan]")
    containers = provision_containers(server_count, ssh_ports, http_ports)

    # Step 6 - Wait for SSH
    console.print("\n[bold cyan]Step 5: Waiting for SSH on all containers...[/bold cyan]")
    for name, ssh_port, http_port in containers:
        console.print(f"\n[dim]Checking SSH on {name} (port {ssh_port})...[/dim]")
        if not wait_for_ssh(host="127.0.0.1", port=ssh_port):
            console.print(f"[red]SSH not ready on {name}. Exiting.[/red]")
            sys.exit(1)

    # Step 7 - Generate inventory
    console.print("\n[bold cyan]Step 6: Generating dynamic inventory...[/bold cyan]")
    generate_inventory(containers)

    # Step 8 - Generate playbook
    console.print("\n[bold cyan]Step 7: Generating Ansible playbook...[/bold cyan]")
    playbook_content = call_openrouter(generate_playbook_prompt(user_input))
    console.print(f"\n[bold green]Generated Playbook:[/bold green]")
    console.print(f"[yellow]{playbook_content}[/yellow]")
    save_playbook(playbook_content)
    console.print(f"\n[green]Playbook saved to {PLAYBOOK_PATH}[/green]")

    # Step 9 - Execute playbook
    console.print("\n[bold cyan]Step 8: Executing playbook against all containers...[/bold cyan]")
    ansible_command = (
        f"ansible-playbook -i {INVENTORY_PATH} {PLAYBOOK_PATH} "
        f"--ssh-extra-args='-o StrictHostKeyChecking=no'"
    )
    exit_code, output = run_command(ansible_command)

    # Step 10 - Show result
    if exit_code == 0:
        console.print(Panel.fit(
            "[bold green]SUCCESS[/bold green]\n"
            f"All {server_count} server(s) provisioned and configured successfully!",
            border_style="green"
        ))
        verify_services(containers)
        console.print("\n[bold white]Access your servers from the host:[/bold white]")
        for name, ssh_port, http_port in containers:
            console.print(f"  [cyan]curl http://127.0.0.1:{http_port}[/cyan]  ← {name}")
    else:
        console.print(Panel.fit(
            "[bold red]FAILED[/bold red]\n"
            "Something went wrong. Check the logs above.",
            border_style="red"
        ))

if __name__ == "__main__":
    main()

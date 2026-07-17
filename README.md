# Ansible AI Agent

> From Prompt to Production — Building AI Agents That Actually Automate Infrastructure Configuration

---

## What Is This?

A Python-based AI agent that takes a plain English infrastructure task, generates a production-safe Ansible playbook using AI, provisions fresh Docker containers, and executes the playbook against them — all from a single prompt.

No manual playbook writing. No pre-configured environments. Everything happens live.

---

## Example Prompts
Install and start nginx on the target server
Install and start apache on 3 servers, deploy default hello world page
Install and start nginx on 2 servers, deploy default page with content "This is demo page created for AI conference."

---

## Project Structure

ansible-ai-agent/
│
├── agent.py                  Main agent controller
├── prompt_template.py        Prompt engineering for AI playbook generation
├── executor.py               Shell command runner and live log streaming
├── inventory.ini             Dynamically generated Ansible inventory
├── Dockerfile                Ubuntu 22.04 SSH target container
├── requirements.txt          Python dependencies
├── .env.example              API key template
├── .gitignore                Excludes .env and output folder
└── output/
└── playbook.yml              AI-generated playbook (git ignored)

---

## Tech Stack

| Component | Technology |
|---|---|
| Agent Controller | Python 3.10+ |
| AI Model | DeepSeek v3 via OpenRouter API |
| Configuration Management | Ansible |
| Target Environment | Docker containers (Ubuntu 22.04) |
| Terminal Output | Rich (Python) |
| Port Management | Dynamic — SSH range 2222-2230, HTTP range 8080-8090 |

---

## Prerequisites

- Python 3.10+
- Docker
- Ansible
- OpenRouter API key (https://openrouter.ai)

---

## Installation

```bash
# Clone the repository
git clone https://gitlab.com/yourusername/ansible-ai-agent.git
cd ansible-ai-agent

# Install Python dependencies
pip3 install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env and add your OpenRouter API key

# Build the Docker target image
docker build -t ansible-target .
```

---

## Running the Agent

```bash
python3 agent.py
```

When prompted, type your infrastructure task in plain English:

Install and start nginx on 2 servers, deploy hello world as default page


---

## What the Agent Does Automatically

- Detects number of servers from your prompt
- Picks available ports from the defined range
- Removes any existing containers for a clean run
- Cleans SSH known hosts for the port range
- Provisions fresh Docker containers with SSH and HTTP exposed
- Waits for SSH to be ready on all containers
- Generates a dynamic Ansible inventory
- Calls DeepSeek AI to generate a production-safe playbook
- Executes the playbook with live coloured output
- Verifies HTTP response on each container
- Prints host access URLs

---

## Configuration

| Variable | Description | Default |
|---|---|---|
| OPENROUTER_API_KEY | Your OpenRouter API key | Required |
| OPENROUTER_MODEL | Model to use | deepseek/deepseek-chat-v3-0324 |

Port ranges can be adjusted in `agent.py`:

```python
SSH_PORT_START = 2222
SSH_PORT_END = 2230
HTTP_PORT_START = 8080
HTTP_PORT_END = 8090
```

---

## License

MIT

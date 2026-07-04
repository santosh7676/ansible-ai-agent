def generate_playbook_prompt(user_input: str) -> str:
    return f"""
You are an expert Ansible automation engineer.

Your job is to generate a production-safe Ansible playbook based on the user's request.

User Request: {user_input}

Rules:
1. Return ONLY valid YAML, no explanations, no markdown, no backticks
2. The playbook must be idempotent
3. Use handlers where appropriate (e.g restart service after config change)
4. Target host group must be: webservers
5. Always include become: true at the play level for privilege escalation
6. Use ansible_python_interpreter: /usr/bin/python3
7. Include proper error handling using block/rescue where needed
8. Add clear task names that describe what each task does
9. Do not use deprecated modules
10. Do NOT include any tasks that reference local files, templates, or Jinja2 (.j2) files
11. Do NOT use the template or copy module with src pointing to local files
12. Only use built-in Ansible modules that do not require external files
13. Keep the playbook simple and self-contained
14. Always use ansible_facts['os_family'] instead of ansible_os_family in when conditions
15. Handlers must NEVER contain when conditions or any conditionals
16. Handlers should only contain the service action, nothing else
17. For nginx on Ubuntu/Debian, always use /var/www/html/index.html as the web root
18. For apache2 on Ubuntu/Debian, always use /var/www/html/index.html as the web root

Return only the playbook YAML starting with ---
"""

def generate_server_count_prompt(user_input: str) -> str:
    return f"""
You are a text parser.

Extract the number of servers/hosts/machines mentioned in the user request below.

User Request: {user_input}

Rules:
1. Return ONLY a single integer number
2. If no number is mentioned, return 1
3. If the user says "a server" or "the server" return 1
4. Do not return any explanation or text, only the number

Examples:
- "Install nginx on 3 servers" -> 3
- "Install nginx on the target server" -> 1
- "Deploy Apache on 5 hosts" -> 5
- "Set up a web server" -> 1

Return only the integer:
"""

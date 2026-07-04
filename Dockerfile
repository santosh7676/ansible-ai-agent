FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Fix clock skew issue for apt inside containers
RUN echo 'Acquire::Check-Valid-Until "false";' > /etc/apt/apt.conf.d/99no-check-valid-until && \
    echo 'Acquire::Check-Date "false";' >> /etc/apt/apt.conf.d/99no-check-valid-until

# Install required packages + pre-cache nginx and apache2
RUN apt-get update && apt-get install -y \
    openssh-server \
    python3 \
    python3-pip \
    sudo \
    curl \
    nginx \
    apache2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Stop services so Ansible can start them cleanly
RUN service nginx stop 2>/dev/null || true && \
    service apache2 stop 2>/dev/null || true

# Create ansible user
RUN useradd -m -s /bin/bash ansible && \
    echo "ansible:ansible" | chpasswd && \
    usermod -aG sudo ansible && \
    echo "ansible ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers

# Setup SSH
RUN mkdir /var/run/sshd && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config && \
    sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config

EXPOSE 22

CMD ["/usr/sbin/sshd", "-D"]

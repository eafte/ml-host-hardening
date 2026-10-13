#!/usr/bin/env bash
# Reproduces the hardening applied to the ml-host VM, in the order it was done.
# STATUS: documents the procedure followed on this VM. It has not been tested
# end to end on a fresh machine. Review before running, and keep a console open.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"

# Refuse to continue without a working key: disabling passwords first locks you out.
if [ ! -s "$HOME/.ssh/authorized_keys" ]; then echo "No SSH key in ~/.ssh/authorized_keys. Install and test a key first."; exit 1; fi

# 1. Patching
sudo apt update && sudo apt full-upgrade -y
sudo install -m 644 "$HERE/apt-20auto-upgrades.conf" /etc/apt/apt.conf.d/20auto-upgrades

# 2. SSH: key-only login
sudo install -m 644 "$HERE/sshd-00-hardening.conf" /etc/ssh/sshd_config.d/00-hardening.conf
sudo sshd -t && sudo systemctl reload ssh

# 3. Firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw limit from 192.168.56.1 to any port 22 proto tcp comment "ssh from admin host"
sudo ufw allow 80/tcp comment "nginx http"
sudo patch -p0 /etc/ufw/sysctl.conf < <(sed "s|^--- .*|--- /etc/ufw/sysctl.conf|" "$HERE/ufw-sysctl.diff")
sudo ufw --force enable

# 4. Kernel settings
sudo install -m 644 "$HERE/sysctl-99-hardening.conf" /etc/sysctl.d/99-hardening.conf
sudo sysctl --system

# 5. fail2ban
sudo apt install -y fail2ban
sudo install -m 644 "$HERE/fail2ban-00-hardening.local" /etc/fail2ban/jail.d/00-hardening.local
sudo systemctl enable --now fail2ban

# 6. Disable crash reporting (it resets fs.suid_dumpable) and unused protocols
sudo systemctl disable --now apport
sudo install -m 644 "$HERE/limits-99-no-core.conf" /etc/security/limits.d/99-no-core.conf
sudo install -m 644 "$HERE/modprobe-99-disable-protocols.conf" /etc/modprobe.d/99-disable-protocols.conf

# 7. Service sandbox
sudo mkdir -p /etc/systemd/system/ml-api.service.d
sudo install -m 644 "$HERE/ml-api-10-sandbox.conf" /etc/systemd/system/ml-api.service.d/10-hardening.conf
sudo install -m 644 "$HERE/ml-api-20-no-core.conf" /etc/systemd/system/ml-api.service.d/20-no-core.conf
sudo systemctl daemon-reload && sudo systemctl restart ml-api

echo "Done. Verify with: sudo ufw status verbose; sudo sshd -T | grep -i passwordauth; systemd-analyze security ml-api"

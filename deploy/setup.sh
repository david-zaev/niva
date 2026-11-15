#!/usr/bin/env bash
# One-time setup of the Niva server (Oracle E2.1.Micro, Ubuntu 22.04). Run as ubuntu with sudo.
set -euxo pipefail
export DEBIAN_FRONTEND=noninteractive

# 1. 2 GB swap: the VM has only 1 GB RAM
if [ ! -f /swapfile ]; then
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
  sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

# 2. Oracle's Ubuntu image blocks everything but SSH in iptables: open 80/443
for p in 80 443; do
  sudo iptables -C INPUT -p tcp --dport $p -j ACCEPT 2>/dev/null || \
    sudo iptables -I INPUT "$(sudo iptables -L INPUT --line-numbers -n | awk '/REJECT/{print $1; exit}')" -m state --state NEW -p tcp --dport $p -j ACCEPT
done
sudo netfilter-persistent save

# 3. Python 3.12 + Caddy
sudo apt-get update -y
sudo apt-get install -y software-properties-common debian-keyring debian-archive-keyring apt-transport-https curl
sudo add-apt-repository -y ppa:deadsnakes/ppa
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --batch --yes --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt-get update -y
sudo apt-get install -y python3.12 python3.12-venv caddy

# 4. App + venv
sudo mkdir -p /opt/niva && sudo chown ubuntu:ubuntu /opt/niva
cp -r ~/niva-deploy/backend /opt/niva/
[ -f /opt/niva/.env ] || touch /opt/niva/.env
python3.12 -m venv /opt/niva/venv
/opt/niva/venv/bin/pip install --upgrade pip
/opt/niva/venv/bin/pip install -r /opt/niva/backend/requirements.txt

# 5. Services
sudo cp ~/niva-deploy/deploy/niva-api.service /etc/systemd/system/
sudo cp ~/niva-deploy/deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl daemon-reload
sudo systemctl enable --now niva-api
sudo systemctl restart caddy
sleep 3
curl -s http://127.0.0.1:8000/health
echo SETUP_DONE

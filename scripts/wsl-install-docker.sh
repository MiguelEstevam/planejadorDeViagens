#!/usr/bin/env bash
# Instala Docker Engine + plugin Compose no Ubuntu (WSL2).
# Uso: bash scripts/wsl-install-docker.sh
# Depois: feche e reabra o terminal WSL (ou: newgrp docker) para usar docker sem sudo.

set -euo pipefail

if [[ ${EUID:-$(id -u)} -eq 0 && -z "${SUDO_USER:-}" ]]; then
  echo "Execute como seu usuário (não como root direto): bash scripts/wsl-install-docker.sh"
  exit 1
fi

TARGET_USER="${SUDO_USER:-$USER}"

if [[ ! -f /etc/os-release ]]; then
  echo "Não encontrei /etc/os-release. Abortando."
  exit 1
fi

# shellcheck source=/dev/null
. /etc/os-release
if [[ "${ID:-}" != "ubuntu" ]]; then
  echo "Este script foi testado para Ubuntu no WSL. ID=${ID:-?}"
  read -r -p "Continuar mesmo assim? [s/N] " ok || true
  if [[ "${ok:-}" != "s" && "${ok:-}" != "S" ]]; then
    exit 1
  fi
fi

need_sudo() {
  if ! sudo -n true 2>/dev/null; then
    echo "Será pedida a senha do sudo para instalar pacotes."
  fi
}

need_sudo
export DEBIAN_FRONTEND=noninteractive

sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
  sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  sudo chmod a+r /etc/apt/keyrings/docker.asc
fi

ARCH="$(dpkg --print-architecture)"
CODENAME="${VERSION_CODENAME:-}"
if [[ -z "$CODENAME" ]]; then
  echo "Não consegui detectar VERSION_CODENAME. Abortando."
  exit 1
fi

echo "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${CODENAME} stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

sudo apt-get update -y
sudo apt-get install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

sudo groupadd -f docker
sudo usermod -aG docker "${TARGET_USER}"

if command -v systemctl >/dev/null 2>&1 && systemctl is-system-running --quiet 2>/dev/null; then
  sudo systemctl enable --now docker
else
  sudo service docker start || true
fi

echo ""
echo "Docker instalado:"
sudo docker --version
sudo docker compose version
echo ""
echo "Próximos passos:"
echo "  1) Feche este terminal WSL e abra outro (ou rode: newgrp docker)"
echo "  2) Na pasta do projeto: docker compose up --build"
echo "  3) Abra http://localhost:8000/"

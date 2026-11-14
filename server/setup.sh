#!/bin/sh
# Install or update sitepull on the web server. Run from this directory as root:
#   sudo ./setup.sh
# Idempotent. Does not touch Caddy (see Caddyfile.sites) or an existing config.
set -eu
cd "$(dirname "$0")"

id sites >/dev/null 2>&1 || useradd --system --user-group --home-dir /srv/sites \
    --no-create-home --shell /usr/sbin/nologin sites
install -d -o sites -g sites -m 755 /srv/sites
install -d -o root -g root -m 755 /usr/local/lib/sitepull /etc/sitepull
install -o root -g root -m 755 sitepull.py /usr/local/lib/sitepull/sitepull.py
install -o root -g root -m 755 sitectl /usr/local/bin/sitectl
install -o root -g root -m 644 sitepull.service sitepull.timer /etc/systemd/system/
if [ ! -e /etc/sitepull/sites.ini ]; then
    install -o root -g root -m 644 sites.ini.example /etc/sitepull/sites.ini
    echo "created /etc/sitepull/sites.ini"
fi
systemctl daemon-reload
systemctl enable --now sitepull.timer
echo "sitepull installed; 'sitectl status' shows what is served"

# BetBoy VPS deployment

The production VPS runs one public Streamlit app and all evidence jobs from
the same persistent checkout. Runtime SQLite files remain untracked but are
backed up transactionally every night. OVH's daily VPS backup is the second
recovery layer.

## Layout

- Application: `/opt/betboy/app`
- Python environment: `/opt/betboy/venv`
- Runtime secrets: `/opt/betboy/app/config.ini` and `/etc/betboy/betboy.env`
- Local database archives: `/var/backups/betboy`
- Reverse proxy: Caddy on ports 80/443
- Streamlit: loopback only on port 8501

## Initial installation

1. Clone the repository to `/opt/betboy/app`.
2. Transfer the ignored runtime databases and `config.ini`.
3. Run `sudo BETBOY_HOST=<hostname> deploy/bootstrap_server.sh`.
4. Verify the app, service status, timers, firewall, TLS and a restore from
   the generated SQLite archive.

The bootstrap disables SSH password login. Confirm key-based SSH access before
running it.

## Updating

After changes have been pushed to `main`:

```bash
cd /opt/betboy/app
sudo deploy/update_server.sh
```

Database files and secrets are ignored by Git and are not changed by updates.

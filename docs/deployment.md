# Deployment Guide

Production deployment strategies for Amiibot.

---

## Deployment Options

### Option 1: Cron Job (Simplest)

Best for: Personal use, simple setups

```bash
# Edit crontab
crontab -e

# Run every 30 minutes
*/30 * * * * cd /path/to/Amiibot && /path/to/Amiibot/.venv/bin/python amiibot.py >> /path/to/Amiibot/cron.log 2>&1
```

**Advantages:**
- ✅ Simple setup
- ✅ No additional services
- ✅ Works on any system with cron

**Disadvantages:**
- ❌ No automatic restart on failure
- ❌ Limited monitoring
- ❌ Manual log management

---

### Option 2: Systemd Service (Recommended)

Best for: Production, 24/7 operation, Linux servers

#### Create Service File

Create `/etc/systemd/system/amiibot.service`:

```ini
[Unit]
Description=Amiibot Stock Notifier
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=amiibot
Group=amiibot
WorkingDirectory=/opt/amiibot
Environment="PATH=/opt/amiibot/.venv/bin"
ExecStart=/opt/amiibot/.venv/bin/python amiibot.py
Restart=on-failure
RestartSec=30
StandardOutput=append:/var/log/amiibot/stdout.log
StandardError=append:/var/log/amiibot/stderr.log

# Security
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/amiibot

[Install]
WantedBy=multi-user.target
```

#### Setup Steps

```bash
# Create user
sudo useradd -r -s /bin/false amiibot

# Create directory
sudo mkdir -p /opt/amiibot
sudo mkdir -p /var/log/amiibot

# Copy files
sudo cp -r /path/to/Amiibot/* /opt/amiibot/

# Set permissions
sudo chown -R amiibot:amiibot /opt/amiibot
sudo chown -R amiibot:amiibot /var/log/amiibot

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable amiibot
sudo systemctl start amiibot

# Check status
sudo systemctl status amiibot
```

#### Service Management

```bash
# Start service
sudo systemctl start amiibot

# Stop service
sudo systemctl stop amiibot

# Restart service
sudo systemctl restart amiibot

# View logs
sudo journalctl -u amiibot -f

# Check status
sudo systemctl status amiibot
```

**Advantages:**
- ✅ Automatic restart on failure
- ✅ Integrated logging
- ✅ System-level management
- ✅ Starts on boot

## Production Checklist

### Pre-Deployment

- [ ] Configuration file created and validated
- [ ] Database configured (PostgreSQL recommended)
- [ ] Messenger webhooks/tokens tested
- [ ] Dependencies installed
- [ ] Logs directory created
- [ ] Permissions set correctly

### Security

- [ ] Config file not world-readable: `chmod 600 config/config.json`
- [ ] Separate user account created
- [ ] No sensitive data in logs
- [ ] Database password secure
- [ ] Webhook URLs kept private

### Monitoring

- [ ] Log rotation configured (automatic with RotatingFileHandler)
- [ ] Disk space monitoring set up
- [ ] Error alerting configured
- [ ] Database backup scheduled

### Performance

- [ ] Appropriate scrape interval set
- [ ] Resource limits configured (systemd)
- [ ] Database optimized
- [ ] Old records cleanup scheduled

---

## Monitoring and Maintenance

### Log Monitoring

```bash
# View recent logs
tail -f /var/log/amiibot/stdout.log

# Check for errors
grep ERROR /opt/amiibot/log.txt

# Log rotation status
ls -lh /opt/amiibot/log.txt*
```

### Database Maintenance

```bash
# SQLite vacuum (optimize)
sqlite3 amiibot.db "VACUUM;"

# PostgreSQL maintenance
psql -U amiibot_user -d amiibot -c "VACUUM ANALYZE;"

# Check database size
du -h amiibot.db  # SQLite
psql -U amiibot_user -d amiibot -c "SELECT pg_size_pretty(pg_database_size('amiibot'));"  # PostgreSQL
```

### Cleanup Old Records

Add to crontab to run weekly:

```bash
# Clean records older than 30 days
0 0 * * 0 cd /opt/amiibot && /opt/amiibot/.venv/bin/python -c "from database import Database; from config.config import load_config; config = load_config('config/config.json'); db = Database(config.database); db.cleanup_old_records(30)" >> /var/log/amiibot/cleanup.log 2>&1
```

---

## Scaling

### Multiple Instances

Run multiple instances for different regions:

```bash
# Instance 1: US stockists
/opt/amiibot-us/
  config/config.json  # US stockists only

# Instance 2: UK stockists
/opt/amiibot-uk/
  config/config.json  # UK stockists only
```

Each with its own systemd service:
- `amiibot-us.service`
- `amiibot-uk.service`

### Load Balancing

For high-volume scraping:
- Use PostgreSQL for shared database
- Run instances on multiple servers
- Coordinate scraping times to avoid overlap

---

## Backup Strategy

### Configuration Backup

```bash
# Backup config (automated)
0 0 * * * cp /opt/amiibot/config/config.json /backup/amiibot-config-$(date +\%Y\%m\%d).json
```

### Database Backup

```bash
# SQLite backup
cp amiibot.db amiibot.db.backup

# PostgreSQL backup
pg_dump -U amiibot_user amiibot > amiibot_backup.sql

# Automated PostgreSQL backup (cron)
0 2 * * * pg_dump -U amiibot_user amiibot | gzip > /backup/amiibot-$(date +\%Y\%m\%d).sql.gz
```

---

## Updates and Upgrades

### Update Amiibot

```bash
# Pull latest code
cd /opt/amiibot
sudo -u amiibot git pull

# Update dependencies
sudo -u amiibot uv sync

# Restart service
sudo systemctl restart amiibot
```

### Database Migration

When upgrading between versions:

```bash
# Backup first!
pg_dump -U amiibot_user amiibot > backup.sql

# Run migrations (if any)
python migrate.py

# Test
python amiibot.py
```

---

## Troubleshooting Production Issues

See [Troubleshooting Guide](troubleshooting.md) for detailed solutions.

### Quick Diagnostics

```bash
# Check service status
sudo systemctl status amiibot

# View recent logs
sudo journalctl -u amiibot -n 100

# Check resource usage
top -p $(pgrep -f amiibot)

# Check disk space
df -h

# Check database connectivity
psql -U amiibot_user -d amiibot -c "SELECT 1;"
```

---

## Best Practices

1. **Use PostgreSQL for Production**: More reliable than SQLite
2. **Monitor Logs Regularly**: Set up log monitoring alerts
3. **Backup Database Weekly**: Automate with cron
4. **Keep Config Secure**: Use proper file permissions
5. **Test Before Deploying**: Run locally first
6. **Document Changes**: Keep deployment notes
7. **Monitor Disk Space**: Logs and database grow over time
8. **Update Regularly**: Stay current with latest version

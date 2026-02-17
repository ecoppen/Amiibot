# Troubleshooting Guide

Common issues and their solutions.

---

## Configuration Issues

### Error: "Configuration file not found"

**Symptom:**
```
ValueError: config/config.json does not exist
```

**Solution:**
```bash
cd config
cp config.example.json config.json
# Edit config.json with your settings
```

---

### Error: "Discord webhook URL may be invalid"

**Symptom:**
```
WARNING - Discord webhook URL may be invalid: https://example.com
```

**Solution:**
Ensure your webhook URL contains `discord.com/api/webhooks/`:
```
https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
```

---

### Error: "Empty stockists list"

**Symptom:**
```
Configuration validation failed:
  - Discord messenger must have at least one stockist configured
```

**Solution:**
Add at least one stockist to your messenger configuration:
```json
{
  "stockists": ["bestbuy.com", "gamestop.com"]
}
```

---

## Database Issues

### Error: "Database connection failed"

**For SQLite:**
- Check file permissions: `ls -l *.db`
- Ensure directory is writable

**For PostgreSQL:**
- Check credentials in config.json
- Test connection: `psql -U username -d amiibot`
- Verify PostgreSQL is running: `systemctl status postgresql`

---

### Error: "Table does not exist"

**Solution:**
Tables are created automatically on first run. If missing:
```python
python -c "from database import Base, Database; from config.config import load_config; config = load_config('config/config.json'); db = Database(config.database); print('Tables created')"
```

---

## Scraping Issues

### Error: "Request timed out"

**Symptom:**
```
WARNING - Request timed out on attempt 1/3
```

**Solution:**
- Check internet connection
- Increase timeout in `constants.py`: `REQUEST_TIMEOUT = 10`
- Retry will happen automatically (3 attempts)

---

### Error: "Selenium exception"

**Symptom:**
```
ERROR - Selenium exception: ...
```

**Solution:**
```bash
# Install Chrome/Chromium
sudo apt install chromium-browser chromium-chromedriver

# Or update chromedriver
pip install --upgrade chromedriver-autoinstaller
```

---

### Error: "No items scraped"

**Possible Causes:**
1. Website structure changed
2. IP blocked by retailer
3. JavaScript not loading

**Solutions:**
- Check logs for specific errors
- Try different network/VPN
- Report issue on GitHub

---

## Notification Issues

### Discord webhook not working

**Check:**
1. Webhook URL is correct
2. Channel still exists
3. Webhook wasn't deleted
4. Bot has permissions

**Test webhook:**
```bash
curl -X POST "YOUR_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -d '{"content": "Test message"}'
```

---

### Telegram bot not responding

**Check:**
1. Bot token is correct
2. Chat ID is correct
3. You sent `/start` to bot
4. Bot isn't blocked

**Test bot:**
```bash
curl "https://api.telegram.org/botYOUR_BOT_TOKEN/getMe"
```

---

## Performance Issues

### High CPU usage

**Causes:**
- Too many stockists
- Selenium driver not closing

**Solutions:**
- Reduce stockist count
- Check `driver.quit()` in logs
- Increase scrape interval in cron

---

### High memory usage

**Causes:**
- Session leaks
- Large log files

**Solutions:**
- Logs rotate automatically (5MB limit)
- Clean old records: See database cleanup methods
- Restart service periodically

---

## Logs and Debugging

### Enable debug logging

Edit `amiibot.py`:
```python
level=os.environ.get("LOGLEVEL", "DEBUG")
```

Or set environment variable:
```bash
LOGLEVEL=DEBUG python amiibot.py
```

---

### View logs

```bash
# Tail logs in real-time
tail -f log.txt

# View last 100 lines
tail -100 log.txt

# Search for errors
grep ERROR log.txt

# Check log rotation
ls -lh log.txt*
```

---

## Common Error Messages

### "Module not found"

**Solution:**
```bash
# Reinstall dependencies
uv sync
# or
pip install -e .
```

---

### "Permission denied"

**Solution:**
```bash
# Fix file permissions
chmod +x amiibot_runner.sh
chmod 644 config/config.json

# Fix directory permissions
chmod 755 /path/to/Amiibot
```

---

### "Port already in use" (PostgreSQL)

**Solution:**
```bash
# Find process using port
sudo lsof -i :5432

# Change port in config if needed
```

---

## Health Checks

Run these commands to verify system health:

```bash
# Check Python version
python --version  # Should be 3.12+

# Check dependencies
pip list | grep -E "beautifulsoup4|selenium|sqlalchemy"

# Check database
sqlite3 amiibot.db ".tables"  # SQLite
psql -U user -d amiibot -c "\dt"  # PostgreSQL

# Test configuration
python -c "from config.config import load_config; load_config('config/config.json'); print('OK')"

# Check logs for errors
grep -i error log.txt | tail -20
```

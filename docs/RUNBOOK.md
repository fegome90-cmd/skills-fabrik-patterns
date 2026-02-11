# Operations Runbook

> Deployment, monitoring, and troubleshooting guide for Skills-Fabrik Patterns plugin.

---

## Overview

This runbook covers operational procedures for maintaining the Skills-Fabrik Patterns plugin in production environments.

| Component | Purpose | Criticality |
|-----------|---------|------------|
| Health Check | Session start validation | High |
| Quality Gates | Pre-session-end validation | Critical |
| Handoff/Backup | State preservation | High |
| TAGs Injection | Context enhancement | Low |

---

## Deployment Procedures

### Initial Installation

```bash
# 1. Navigate to plugins directory
cd ~/.claude/plugins

# 2. Clone repository
git clone https://github.com/fegome90-cmd/skills-fabrik-patterns.git
cd skills-fabrik-patterns

# 3. Run installer
python3 setup.py

# 4. Enable plugin in settings
# Edit ~/.claude/settings.json:
{
  "enabledPlugins": {
    "skills-fabrik-patterns@local": true
  }
}

# 5. Restart Claude Code
# Verify plugin loads by checking startup messages
```

### Upgrading Plugin

```bash
# 1. Navigate to plugin directory
cd ~/.claude/plugins/skills-fabrik-patterns

# 2. Stash local changes (if any)
git stash

# 3. Pull latest changes
git pull origin main

# 4. Update dependencies
pip install -r requirements.txt --upgrade

# 5. Run tests to verify
pytest --cov=lib

# 6. Restart Claude Code
```

### Rolling Back

```bash
# 1. Navigate to plugin directory
cd ~/.claude/plugins/skills-fabrik-patterns

# 2. View commit history
git log --oneline -10

# 3. Checkout previous version
git checkout <commit-sha>

# 4. Restart Claude Code
```

---

## Monitoring and Alerts

### Health Status Monitoring

```bash
# Run health check manually
python3 scripts/health-check.py

# Expected output (healthy):
{
  "status": "healthy",
  "checks": [
    {"name": "python_version", "status": "healthy", "message": "..."},
    {"name": "plugin_integrity", "status": "healthy", "message": "..."},
    {"name": "context_integrity", "status": "healthy", "message": "..."},
    {"name": "memory_usage", "status": "healthy", "message": "..."},
    {"name": "disk_space", "status": "healthy", "message": "..."}
  ]
}
```

### Backup Verification

```bash
# List recent backups
ls -lt ~/.claude/backups/ | head -10

# Verify backup metadata
cat ~/.claude/backups/<timestamp>/metadata.json

# Check backup size
du -sh ~/.claude/backups/<timestamp>
```

### Handoff Verification

```bash
# List recent handoffs
ls -lt ~/.claude/handoffs/ | head -10

# View handoff content
cat ~/.claude/handoffs/handoff-<timestamp>.md
```

### Log Monitoring

```bash
# Claude Code logs
tail -f ~/.claude/logs/*.log

# Plugin logs (if enabled)
tail -f ~/.claude/plugins/skills-fabrik-patterns/.claude-plugin/logs/*.log

# System logs for hook execution
journalctl -u claude-code -f  # If running as service
```

---

## Common Issues and Fixes

### Issue: Hooks Not Firing

**Symptoms:**
- No health check output on session start
- No quality gates on session end
- No handoff/backup created

**Diagnosis:**
```bash
# Check plugin is enabled
cat ~/.claude/settings.json | grep skills-fabrik

# Verify hook configuration
cat .claude-plugin/hooks/hooks.json

# Check for syntax errors in scripts
python3 -m py_compile scripts/*.py
```

**Fixes:**
1. Enable plugin in settings.json
2. Verify scripts are executable: `chmod +x scripts/*.py`
3. Check Python version: `python3 --version` (must be 3.10+)

### Issue: Quality Gates Timing Out

**Symptoms:**
- Gates show "timeout" status
- Session end takes too long

**Diagnosis:**
```bash
# Run gates manually to measure timing
time python3 scripts/quality-gates.py

# Check gate timeout settings
cat config/gates.yaml | grep timeout
```

**Fixes:**
1. Increase timeout in `config/gates.yaml`
2. Optimize slow gate commands
3. Set `parallel: true` in orchestrator

### Issue: Handoff Not Created

**Symptoms:**
- No handoff files in `~/.claude/handoffs/`
- Session context lost between sessions

**Diagnosis:**
```bash
# Run handoff script manually
python3 scripts/handoff-backup.py

# Check permissions
ls -la ~/.claude/handoffs/
```

**Fixes:**
1. Create handoffs directory: `mkdir -p ~/.claude/handoffs`
2. Check write permissions
3. Verify handoff.py has no syntax errors

### Issue: Backup Fails

**Symptoms:**
- No backup directories created
- Restore command not available

**Diagnosis:**
```bash
# Check disk space
df -h ~/.claude/backups/

# Run backup manually
python3 -c "from lib.backup import StateBackup; StateBackup().create_default_backup()"
```

**Fixes:**
1. Free up disk space
2. Check backup directory permissions
3. Verify backup.py module is working

### Issue: TAGs Not Injected

**Symptoms:**
- No semantic context in prompts
- TAGs markers missing from output

**Diagnosis:**
```bash
# Test TAG injector
python3 -c "from lib.tag_system import TagInjector; print(TagInjector().inject('test'))"

# Check context files exist
ls -la ~/.claude/.context/
```

**Fixes:**
1. Verify context files exist (identity.md, projects.md, etc.)
2. Check tag_system.py for errors
3. Ensure inject-context.py is executable

### Issue: High Memory Usage

**Symptoms:**
- Claude Code process using excessive memory
- System slows during session

**Diagnosis:**
```bash
# Check memory usage
ps aux | grep claude

# Run health check for memory details
python3 scripts/health-check.py | jq '.checks[] | select(.name=="memory_usage")'
```

**Fixes:**
1. Clear old backups: Remove old directories in `~/.claude/backups/`
2. Clear old handoffs: Remove old files in `~/.claude/handoffs/`
3. Restart Claude Code periodically

---

## Rollback Procedures

### State Rollback

When something goes wrong and you need to restore previous state:

```bash
# 1. List available backups
ls -la ~/.claude/backups/

# 2. Find the backup ID (directory name is timestamp: YYYYMMDD-HHMMSS)
# Example: 20260210-115952

# 3. Use the restore command from backup metadata
cat ~/.claude/backups/20260210-115952/metadata.json | jq .restore_command

# 4. Execute the restore command
python3 ~/.claude/plugins/skills-fabrik-patterns/scripts/backup-state.py --restore 20260210-115952

# 5. Verify restore completed
ls -la ~/.claude/.context/
```

### Plugin Rollback

If a plugin update causes issues:

```bash
# 1. Navigate to plugin directory
cd ~/.claude/plugins/skills-fabrik-patterns

# 2. View git history
git log --oneline -10

# 3. Checkout previous commit
git checkout abc1234

# 4. Restart Claude Code
```

### Emergency Rollback

Quick rollback to last known good state:

```bash
# Find most recent backup
BACKUP_ID=$(ls -t ~/.claude/backups/ | head -1)

# Restore it
python3 ~/.claude/plugins/skills-fabrik-patterns/lib/backup.py --restore "$BACKUP_ID"
```

---

## Maintenance Tasks

### Daily Checks

- [ ] Verify health check passes
- [ ] Check no critical gate failures
- [ ] Verify backup was created

### Weekly Tasks

```bash
# Clean up old backups (keep last 10)
cd ~/.claude/backups/
ls -t | tail -n +11 | xargs rm -rf

# Clean up old handoffs (keep last 20)
cd ~/.claude/handoffs/
ls -t | tail -n +21 | xargs rm -rf
```

### Monthly Tasks

```bash
# Review and update quality gates
nano config/gates.yaml

# Review and update alert thresholds
nano config/alerts.yaml

# Check for plugin updates
cd ~/.claude/plugins/skills-fabrik-patterns
git fetch origin
git log HEAD..origin/main --oneline
```

---

## Performance Tuning

### Quality Gate Optimization

```yaml
# In config/gates.yaml
gates:
  - name: my-gate
    timeout: 30000      # Reduce if gate is fast
    file_patterns: ["*.py"]  # Be specific to reduce runs
```

### Alert Threshold Tuning

```yaml
# In config/alerts.yaml
thresholds:
  critical:
    failure_rate: 0.5  # Adjust based on project needs
```

### Memory Optimization

```bash
# Limit backup retention
python3 -c "from lib.backup import StateBackup; s = StateBackup(); s.cleanup_old_backups(keep=5)"

# Clear context cache
rm -rf ~/.claude/.context/__pycache__/
```

---

## Security Considerations

### Secrets Detection

The security-check gate looks for:
- `API_KEY`
- `SECRET`
- `PASSWORD`
- `TOKEN`

**If false positives occur:**
1. Add exclusions to gate command
2. Use environment variables instead
3. Add file to .gitignore

### Backup Security

Backups may contain sensitive information:

```bash
# Set proper permissions
chmod 700 ~/.claude/backups/
chmod 600 ~/.claude/backups/*/*

# Encrypt backups if needed (external tool)
# gpg --encrypt ~/.claude/backups/<timestamp>/*
```

---

## Contact and Support

| Issue Type | Contact |
|------------|---------|
| Bug reports | GitHub Issues |
| Feature requests | GitHub Discussions |
| Security issues | GitHub Security Advisories |
| Questions | GitHub Discussions |

---

## Appendix: Quick Reference Commands

```bash
# Health check
python3 scripts/health-check.py

# Quality gates
python3 scripts/quality-gates.py

# Handoff + backup
python3 scripts/handoff-backup.py

# Restore from backup
python3 lib/backup.py --restore <timestamp>

# List backups
ls -la ~/.claude/backups/

# List handoffs
ls -la ~/.claude/handoffs/

# Run tests
pytest --cov=lib

# Type check
mypy lib/ scripts/

# Clean old backups
rm -rf ~/.claude/backups/$(ls -t ~/.claude/backups/ | tail -n +11)
```

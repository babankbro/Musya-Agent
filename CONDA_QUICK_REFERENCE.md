# Conda Quick Reference - Musya Agent

## 🚀 Essential Commands

### Initial Setup

```powershell
# Install Miniconda (if not installed)
# Download from: https://docs.conda.io/en/latest/miniconda.html

# Initialize Conda for PowerShell (one-time setup)
conda init powershell

# Restart PowerShell after initialization
```

### Create Environment

```powershell
# Create environment from environment.yml
conda env create -f environment.yml

# This creates 'musya-agent' environment with Python 3.12 and all dependencies
```

### Activate/Deactivate

```powershell
# Activate environment
conda activate musya-agent

# Deactivate environment
conda deactivate

# Check current environment
conda info --envs
```

### Update Environment

```powershell
# Update environment with new dependencies
conda env update -f environment.yml --prune

# The --prune flag removes packages not in environment.yml
```

### Remove Environment

```powershell
# Remove environment completely
conda env remove -n musya-agent

# Then recreate
conda env create -f environment.yml
```

### List Packages

```powershell
# List all packages in current environment
conda list

# List pip packages only
pip list

# Search for specific package
conda list | findstr fastapi
```

### Install Additional Packages

```powershell
# Activate environment first
conda activate musya-agent

# Install via pip (recommended for Python packages)
pip install package-name

# Install via conda
conda install package-name
```

## 📋 Common Workflows

### Daily Development

```powershell
# 1. Activate environment
conda activate musya-agent

# 2. Start Docker services
docker-compose up -d postgres minio

# 3. Run your scripts
python scripts\check_database.py
python -m uvicorn src.main:app --reload
```

### Update Dependencies

```powershell
# 1. Edit environment.yml (add/update packages)

# 2. Update environment
conda env update -f environment.yml --prune

# 3. Verify
conda list
```

### Fresh Start

```powershell
# 1. Remove old environment
conda env remove -n musya-agent

# 2. Recreate from environment.yml
conda env create -f environment.yml

# 3. Activate
conda activate musya-agent

# 4. Verify
python --version
conda list
```

## 🔍 Troubleshooting

### Conda not recognized

```powershell
# Initialize conda for PowerShell
conda init powershell

# Restart PowerShell
# Then try again
```

### Environment activation fails

```powershell
# Check if environment exists
conda env list

# If exists, try full path
conda activate musya-agent

# If not exists, create it
conda env create -f environment.yml
```

### Package conflicts

```powershell
# Remove environment and recreate
conda env remove -n musya-agent
conda env create -f environment.yml

# Or update with prune
conda env update -f environment.yml --prune
```

### Python version mismatch

```powershell
# Check Python version in environment
conda activate musya-agent
python --version

# Should show Python 3.12.x
# If not, recreate environment
```

## 📦 Environment.yml Structure

```yaml
name: musya-agent
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.12
  - pip>=24.0
  - pip:
    - fastapi>=0.135.3
    - crewai>=1.13.0
    # ... other packages
```

**Key points:**
- `name`: Environment name
- `channels`: Where to get packages
- `dependencies`: Conda packages
- `pip`: Python packages installed via pip

## 🎯 Best Practices

1. **Always activate before working**
   ```powershell
   conda activate musya-agent
   ```

2. **Use environment.yml for dependencies**
   - Don't manually install packages
   - Add to environment.yml and update

3. **Keep environment.yml in version control**
   - Ensures reproducibility
   - Team members use same versions

4. **Periodically clean up**
   ```powershell
   # Remove unused packages
   conda clean --all
   ```

5. **Export environment for sharing**
   ```powershell
   # Export current environment
   conda env export > environment-backup.yml
   ```

## 🔗 Useful Links

- **Conda Documentation:** https://docs.conda.io/
- **Conda Cheat Sheet:** https://docs.conda.io/projects/conda/en/latest/user-guide/cheatsheet.html
- **Miniconda Download:** https://docs.conda.io/en/latest/miniconda.html
- **Anaconda Download:** https://www.anaconda.com/download

---

**Quick Setup Reminder:**
```powershell
# 1. Install Miniconda
# 2. conda init powershell
# 3. Restart PowerShell
# 4. conda env create -f environment.yml
# 5. conda activate musya-agent
# 6. python scripts\check_database.py
```

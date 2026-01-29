# Running PDF Optimizer in WSL

## Installation Steps

### 1. Install qpdf in WSL

**Option A: Using apt (Ubuntu/Debian)**
```bash
wsl
sudo apt-get update
sudo apt-get install -y qpdf
```

**Option B: Using the install script**
```bash
wsl bash scripts/install_qpdf_wsl.sh
```

### 2. Verify Installation
```bash
wsl qpdf --version
```

### 3. Install Python Dependencies (if not already installed)
```bash
wsl
cd /mnt/c/Users/roywa/Documents/CursorProjects/MindGraph
conda activate python3.13  # or your Python environment
pip install PyPDF2
```

## Running Scripts in WSL

### Test PDF Optimizer
```bash
wsl bash -c "cd /mnt/c/Users/roywa/Documents/CursorProjects/MindGraph && conda activate python3.13 && python scripts/test_pdf_optimizer.py"
```

### Import PDFs with Optimization
```bash
wsl bash -c "cd /mnt/c/Users/roywa/Documents/CursorProjects/MindGraph && conda activate python3.13 && python scripts/library_import.py import --optimize-pdfs"
```

### Analyze PDF Structure
```bash
wsl bash -c "cd /mnt/c/Users/roywa/Documents/CursorProjects/MindGraph && conda activate python3.13 && python scripts/analyze_pdf_structure_simple.py"
```

## Notes

- WSL paths: Use `/mnt/c/...` to access Windows C: drive
- Python environment: Make sure conda/python is accessible in WSL
- File paths: PDF files should be accessible from WSL (either in WSL filesystem or via /mnt/c/)

## Troubleshooting

**qpdf not found:**
- Make sure qpdf is installed: `sudo apt-get install -y qpdf`
- Check PATH: `which qpdf`

**Python not found:**
- Install Python in WSL or use Windows Python via WSL
- Or use: `wsl python3 scripts/test_pdf_optimizer.py`

**Permission denied:**
- Make scripts executable: `chmod +x scripts/*.sh`
- Check file permissions on PDF files

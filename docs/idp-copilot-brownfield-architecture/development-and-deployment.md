# Development and Deployment

## Local Development Setup

**Actual Working Steps (Windows PowerShell):**
1. `uv venv .venv` - Create virtual environment
2. `. .\.venv\Scripts\Activate.ps1` - Activate environment
3. `uv pip install -r .\capstone\prototype\requirements.txt` - Install dependencies
4. Set `OPENAI_API_KEY` environment variable
5. `python .\capstone\prototype\idp.py` - Run CLI with Prometheus
6. `streamlit run .\capstone\frontend\streamlit_app.py` - Run frontend (separate terminal)

**Known Setup Issues:**
- Requires PowerShell-specific activation syntax
- Multiple requirements.txt files (prototype vs. pyproject.toml)
- Manual environment variable configuration

## Build and Deployment Process

- **Development Commands** (from CLAUDE.md):
  ```powershell
  uv run black .          # Code formatting
  uv run ruff check .     # Linting
  uv run pytest -q       # Testing
  ```
- **No Production Deployment**: Currently single-machine, local development only
- **Containerization**: No Docker support implemented
- **CI/CD**: No automated build/deploy pipeline
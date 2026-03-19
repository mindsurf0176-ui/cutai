# Contributing to CutAI

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
# Clone the repo
git clone https://github.com/minseo-ai/cutai.git
cd cutai

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install with dev dependencies
pip install -e ".[dev]"

# Install FFmpeg (if not already installed)
brew install ffmpeg          # macOS
# sudo apt install ffmpeg    # Ubuntu/Debian

# Verify everything works
pytest tests/ -v
ruff check cutai/
mypy cutai/ --ignore-missing-imports
```

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_types.py -v

# With coverage
pytest tests/ --cov=cutai --cov-report=term-missing
```

Tests use synthetic data and do not require FFmpeg or actual video files.

## Code Style

- **Formatter:** We use `ruff` for linting and formatting
- **Type hints:** All public functions should have type annotations
- **Docstrings:** Google-style docstrings for public APIs
- **Models:** Use Pydantic v2 `BaseModel` for data structures

```bash
# Lint
ruff check cutai/

# Auto-fix
ruff check cutai/ --fix

# Type check
mypy cutai/ --ignore-missing-imports
```

## Adding a New Edit Operation

1. **Define the model** in `cutai/models/types.py`:
   ```python
   class MyOperation(BaseModel):
       type: Literal["myop"] = "myop"
       # ... your fields
   ```

2. **Add it to `EditOperation` union** in `types.py`

3. **Implement the editor** in `cutai/editor/my_editor.py`

4. **Register in the renderer** — update `cutai/editor/renderer.py` to handle your operation type

5. **Add rule-based patterns** (optional) — add keyword matching in `cutai/planner/edit_planner.py`

6. **Write tests** in `tests/test_my_operation.py`

## Creating Style Presets

Style presets are YAML files in `cutai/style/presets/`. To create one:

1. Extract a style: `cutai style-extract reference_video.mp4 -o my-preset.yaml`
2. Edit the YAML to fine-tune values
3. Place it in `cutai/style/presets/`
4. Submit a PR with a descriptive name and `description` field

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Run tests: `pytest tests/ -v`
5. Run lints: `ruff check cutai/`
6. Commit with a clear message
7. Push and open a PR

### PR Guidelines

- Keep PRs focused — one feature or fix per PR
- Add tests for new functionality
- Update README if adding user-facing features
- Don't break existing tests

## Reporting Bugs

Open an issue with:
- CutAI version (`cutai --version`)
- Python version (`python --version`)
- FFmpeg version (`ffmpeg -version`)
- OS and hardware
- Steps to reproduce
- Expected vs actual behavior

## Questions?

Open a discussion on GitHub or file an issue. We're happy to help!

# CAPS Project

Welcome to CAPS! This is a modular Python project using modern tooling.

## Quick Start

### 1. Set up environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"
```

### 2. Configure API key

```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your Google AI API key
# Get your key from: https://makersuite.google.com/app/apikey
```

### 3. Run the demo

```bash
python -m caps.main
```

### 4. Run tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=caps

# Run specific test file
pytest tests/test_schema_validation.py -v
```

## Project Structure

```
CAPS/
├── src/caps/           # Main package
│   ├── agent/         # LLM intent interpreter
│   ├── schema/        # JSON schema validation
│   └── main.py        # CLI entry point
├── tests/             # Test suite
├── config/            # Configuration files
├── pyproject.toml     # Project metadata
└── .env              # Environment variables (not in git)
```

## Phase 1 Status

✅ Python project infrastructure  
✅ Pydantic payment intent schema  
✅ Schema validator (Trust Gate 1)  
✅ Gemini-based intent interpreter  
✅ CLI demo application  
✅ Unit and integration tests

## Next Steps

- Phase 2: Context Engineering
- Phase 3: Policy Engine
- Phase 4: Control Flow & Execution

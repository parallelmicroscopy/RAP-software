# RAP LabThings Wrapper

## Run the server
Use the repository's `python` interpreter path setup so `rap_labthings` is importable:

```bash
PYTHONPATH=python python -m uvicorn rap_labthings.app:app --reload
```

To start the wrapper without hardware:

```bash
RAP_LABTHINGS_SIMULATION=1 PYTHONPATH=python python -m uvicorn rap_labthings.app:app --reload
```

## Phase 1 API surface
- LabThings properties:
  - `GET /rap/status`
  - `GET /rap/config`
- LabThings action:
  - `POST /rap/capture_frame`
- Synchronous FastAPI mirror for direct HTTP error mapping:
  - `POST /rap/capture_frame_sync`

## Run the tests
Run the new wrapper tests and the existing RAP Python tests with the `python` interpreter:

```bash
python -m pytest -q tests/python_tests/test_rap_labthings.py tests/python_tests/test_vimba_rap3.py
```

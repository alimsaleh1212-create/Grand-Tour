"""Backend test package.

Layout follows the AIE guidelines §9: every module under `app/` has a
matching test file.

    tests/unit/          fast, no I/O, mocked externals (schemas,
                         services, tool logic w/ fake LLM).
    tests/integration/   FastAPI TestClient + transactional DB session.
    tests/e2e/           full agent run with mocked Gemini + mocked HTTP.

Naming: file `test_<module>.py`, function `test_<behavior>_<condition>`.
"""

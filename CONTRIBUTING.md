# Contributing to BixDot

BixDot is built and owned by **DigiTech Business Pte. Ltd** (Singapore).
We build in the open and want the best contributors working on local AI.

---

## Before You Contribute

### 1. Sign the CLA (required)

We require a Contributor License Agreement before merging any PR.
It's a one-time, 2-minute process.

**Sign here: [cla.bixdot.app](https://cla.bixdot.app)**

**What it means in plain English:**
- You keep copyright of your contribution
- You grant DigiTech Business Pte. Ltd a permanent license to use it
- You confirm the code is your original work
- Without the CLA, we legally cannot merge your PR

### 2. Check existing issues

Before building something, open an issue or check if one already exists.
We don't want you to spend time on something we're already building.

---

## What We're Looking For

**High priority (we will merge fast):**
- Bug fixes with clear reproduction steps
- Security improvements (coordinate via security@bixdot.app first)
- Performance improvements with benchmarks
- New skills (file management, calendar, messaging)
- Windows/Mac/Linux compatibility fixes
- Documentation improvements

**Low priority (discuss first):**
- Architectural changes
- New dependencies
- UI redesigns

**Will not merge:**
- Code that adds cloud dependencies as defaults
- Anything that reduces local-first guarantees
- PRs without tests for new functionality
- PRs without the CLA signed

---

## Development Setup

```bash
git clone https://github.com/bixdot-app/bixdot.git
cd bixdot
pip install -r requirements.txt

# You need Ollama running locally
ollama pull llama3.2

# Run
python -m core.main
```

---

## Code Standards

**Local first — always**
Never add cloud dependencies as a default. Cloud is opt-in, never opt-out.

**Security by default**
- Every new route must go through `require_auth`
- Every file operation must check permissions
- Every external action must be logged to the audit log
- New capabilities must be added to `Capability` enum and default to denied

**Code style**
- Python 3.11+
- Type hints on all function signatures
- Docstrings on all public functions
- No line over 100 characters

**Testing**
- Tests required for all new functionality
- Security-critical code requires both unit and integration tests
- Run `pytest` before submitting

---

## Submitting a Pull Request

1. Fork the repo
2. Create a branch: `git checkout -b feat/your-feature`
3. Write your code + tests
4. Run `pytest` — all tests must pass
5. Submit the PR with a clear description
6. Confirm CLA is signed in the PR description

---

## Security Issues

**Do not open a public issue for security vulnerabilities.**

Email: **security@bixdot.app**

We respond within 48 hours.
We credit every researcher in our changelog.
We have a responsible disclosure policy in [.github/SECURITY.md](.github/SECURITY.md).

---

## Questions?

- General: [hello@bixdot.app](mailto:hello@bixdot.app)
- GitHub Discussions: [github.com/bixdot-app/bixdot/discussions](https://github.com/bixdot-app/bixdot/discussions)

---

© 2026 DigiTech Business Pte. Ltd · Singapore · [bixdot.app](https://bixdot.app)

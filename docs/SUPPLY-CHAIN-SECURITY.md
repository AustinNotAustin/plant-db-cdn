# Software Supply Chain Security (OWASP A06:2025)

This project follows the **Investigation-First Hardening** approach to prevent software supply chain failures.

## 1. Dependency Management Strategy

### TLDR:
- Add dependency to `requirements.in`
- Run: `./.venv/bin/pip-compile --generate-hashes --allow-unsafe requirements.in --output-file requirements.txt`
- Install: `./.venv/bin/python -m pip install --require-hashes -r requirements.txt`
- Audit: `./scripts/security-scan.sh`

### Python (Mock CDN Application)
- **Source**: `requirements.in` (Direct dependencies only).
- **Lockfile**: `requirements.txt` (Generated with SHA256 hashes for integrity).
- **Workflow**:
    1. Add package to `requirements.in`.
    2. Run `pip-compile --generate-hashes --allow-unsafe requirements.in --output-file requirements.txt` to update the lockfile.
    3. Installation uses `pip install --require-hashes` to guarantee byte-for-byte correctness and prevent substitution attacks.

## 2. Security Auditing

We use a unified scanning entrypoint: `./scripts/security-scan.sh`.

### Tools Integrated:
- **pip-audit**: Checks Python dependencies against the PyPA advisory database (Google OSV). No login required.

## 3. Storage and Data Hardening (Mock CDN Specific)

- **EXIF Stripping**: The application automatically strips metadata from all uploaded images using Pillow to prevent data leakage (location, camera info).
- **Mock S3 Structure**: Simulates partitioned storage (`storage/`, `thumbnails/`, `large/`) to isolate processed assets.

## 4. CI/CD Integration (GitHub Actions)

To automate this, add the following to your `.github/workflows/security.yml`:

```yaml
name: Supply Chain Scan
on: [push, pull_request]

jobs:
  security-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.13'
          
      - name: Install Scan Tools
        run: pip install pip-audit
        
      - name: CDN Application Audit
        run: pip-audit -r requirements.txt
```


## 5. Handling Vulnerabilities

1. **High/Critical detected**: Fail the build.
2. **If patch exists**: Update `requirements.in` or `package.json` and re-lock.
3. **If no patch exists (Upstream OS)**: 
    - Verify if the package is truly needed.
    - If needed, document as a "Known Risk" until a patch is released.
    - Monitor `scripts/security-scan.sh` weekly.

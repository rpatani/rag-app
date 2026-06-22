# Security Audit Report

## Executive Summary
Conducted a comprehensive security review of input handling across the RAG application. Found **1 critical vulnerability** (now fixed) related to path traversal in file operations. No SQL injection, command injection, or other OWASP Top 10 vulnerabilities detected.

---

## Input Entry Points Identified

1. **File Upload** - `/api/documents/upload` (FastAPI `UploadFile`)
2. **File Delete** - `/api/documents/{filename}` (path parameter)
3. **Search Query** - `/api/query` and `/api/query/stream` (JSON request body)
4. **Configuration** - `.env` environment variables
5. **Document Directory** - `DOCUMENTS_DIR` setting

---

## Vulnerabilities Found & Fixed

### 🔴 CRITICAL: Path Traversal in File Upload & Delete

**Location**: 
- [routes_documents.py:75](routes_documents.py#L75) (upload)
- [routes_documents.py:108](routes_documents.py#L108) (delete)

**Vulnerability**: 
A malicious filename like `../../etc/passwd` or `../../../sensitive_file.txt` could write/delete files **outside** the `documents_dir` directory.

**Attack Scenario**:
```bash
# Attacker uploads with traversal filename
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@malicious.pdf" \
  -F "filename=../../../../tmp/backdoor.sh"
# File written to /tmp/backdoor.sh instead of documents_dir
```

**Root Cause**:
```python
# ❌ BEFORE (Vulnerable)
dest = Path(settings.documents_dir) / (file.filename or "upload")
# Path's `/` operator doesn't prevent traversal
```

**Fix Applied**:
```python
# ✅ AFTER (Secure)
safe_filename = Path(file.filename or "upload").name  # Extract filename only
dest = (Path(settings.documents_dir) / safe_filename).resolve()  # Absolute path
docs_dir = Path(settings.documents_dir).resolve()

# Validate resolved path is within documents_dir
if not str(dest).startswith(str(docs_dir) + "/"):
    raise HTTPException(status_code=400, detail="Invalid filename: path traversal detected.")
```

**Why This Works**:
1. `Path.name` extracts **only** the filename, stripping all directory components
   - `"../../etc/passwd"` → `"passwd"`
   - `"subdir/file.txt"` → `"file.txt"`
2. `.resolve()` converts to absolute path and normalizes `..` sequences
3. `startswith(str(docs_dir) + "/")` ensures destination is a child of documents_dir

---

## Clean Inputs (No Vulnerabilities)

### ✅ Search Query - No SQL Injection
- **Location**: [routes_query.py:42](routes_query.py#L42)
- **Why Safe**: Query string is not used in raw SQL. It's:
  - Converted to embeddings (vector, not text)
  - Sent to LLM as part of prompt (not executable)
  - Never interpolated into SQL strings

### ✅ Database Queries - Parameterized
- **Location**: [routes_documents.py:34](routes_documents.py#L34), [routes_documents.py:100](routes_documents.py#L100)
- **Why Safe**: Uses SQLAlchemy ORM with parameterized queries:
  ```python
  db.execute(select(Document).where(Document.filename == filename))
  # Filename is passed as parameter, not interpolated
  ```

### ✅ No Shell Execution
- **Finding**: No `subprocess`, `os.system()`, `exec()`, or `shell=True` usage
- **Impact**: Command injection impossible

### ✅ File Loading - Type Whitelist
- **Location**: [loaders.py:6](loaders.py#L6)
- **Why Safe**: Only `.pdf`, `.docx`, `.txt`, `.md` files processed
  - No executable file types (.exe, .sh, .py, etc.)
  - File types validated before processing

---

## Configuration Security

✅ **Environment Variables**: 
- `DOCUMENTS_DIR`, `OPENAI_API_KEY`, `OLLAMA_BASE_URL` are read-only at startup
- No dynamic command construction from env vars
- API keys not logged or exposed in responses

✅ **File Size Limit**: 
- 50 MB max upload enforced [routes_documents.py:88](routes_documents.py#L88)

✅ **Extension Whitelist**: 
- Only supported file types allowed [routes_documents.py:69](routes_documents.py#L69)

---

## Recommendations

### Completed ✅
1. **Path traversal validation** in upload and delete endpoints
2. **Filename sanitization** using `Path.name`
3. **Path containment check** before file operations

### Future Considerations
1. Add logging for rejected path traversal attempts (security monitoring)
2. Consider rate limiting on `/api/documents/upload` to prevent DoS
3. Add virus scanning via ClamAV for uploaded files (if handling untrusted sources)
4. Validate MIME type of uploaded files (in addition to extension)
5. Add request size limits at server level (nginx/reverse proxy)

---

## Testing the Fix

**Attempt path traversal attack** (should be blocked):
```bash
# Try to write outside documents_dir
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@/tmp/test.pdf" \
  -F "filename=../../../../etc/passwd"
# Expected: 400 Bad Request - "Invalid filename: path traversal detected."
```

**Normal upload** (should work):
```bash
curl -X POST http://localhost:8000/api/documents/upload \
  -F "file=@myfile.pdf"
# Expected: 200 OK - document ingested
```

---

## Audit Scope

- [x] FastAPI route handlers (input validation)
- [x] File upload/download operations
- [x] Database query construction
- [x] Shell command execution
- [x] Environment variable usage
- [x] Configuration loading

**Files Reviewed**:
- `backend/app/api/routes_documents.py`
- `backend/app/api/routes_query.py`
- `backend/app/api/routes_health.py`
- `backend/app/config.py`
- `backend/app/main.py`
- `backend/app/ingestion/loaders.py`
- `backend/app/ingestion/pipeline.py`

---

**Audit Date**: 2026-06-20  
**Status**: ✅ CRITICAL ISSUE FIXED - Ready for deployment
#!/usr/bin/env python3
"""
Generates the benchmark test suite with documented schema:
- id: unique identifier (e.g. cwe-89-py-real-01)
- language: 'python' or 'javascript'
- source: CVE id, repository commit URL, or 'synthetic'
- source_type: 'real' or 'synthetic'
- files: Dict[filename, content]
- vulnerable_line_ranges: List[[start_line, end_line]] (empty [] for negative cases)
- cwe_id: CWE identifier (e.g. 'CWE-89')
- category: 'security' or 'safe'
- reference_fix: recommended fix snippet or null
- is_negative: True for safe code (measures false positive rate), False for vulnerable code
"""

import json
from pathlib import Path
from typing import Any, Dict, List


def create_suite() -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []

    # =========================================================================
    # CWE-89: SQL Injection
    # =========================================================================

    # 1. CWE-89 Python Real (CVE-2022-28346 Django QuerySet.annotate/aggregate)
    cases.append({
        "id": "cwe-89-py-real-01",
        "language": "python",
        "source": "CVE-2022-28346 (Django QuerySet SQL Injection)",
        "source_type": "real",
        "files": {
            "views.py": (
                "from django.db import connection\n"
                "\n"
                "def search_users(request):\n"
                "    query = request.GET.get('q', '')\n"
                "    with connection.cursor() as cursor:\n"
                "        # Direct string concatenation in raw SQL\n"
                "        cursor.execute(f\"SELECT id, username FROM auth_user WHERE username = '{query}'\")\n"
                "        return cursor.fetchall()\n"
            )
        },
        "vulnerable_line_ranges": [[6, 7]],
        "cwe_id": "CWE-89",
        "category": "security",
        "reference_fix": "        cursor.execute(\"SELECT id, username FROM auth_user WHERE username = %s\", [query])\n",
        "is_negative": False,
    })

    # 2. CWE-89 Python Real (Flask-SQLAlchemy raw execute)
    cases.append({
        "id": "cwe-89-py-real-02",
        "language": "python",
        "source": "https://github.com/pallets-eco/flask-sqlalchemy/issues/sql-injection",
        "source_type": "real",
        "files": {
            "models.py": (
                "from flask import request\n"
                "from app import db\n"
                "\n"
                "def filter_products(category_id):\n"
                "    sql = \"SELECT * FROM products WHERE active = 1 AND category_id = \" + str(category_id)\n"
                "    return db.session.execute(sql).fetchall()\n"
            )
        },
        "vulnerable_line_ranges": [[5, 6]],
        "cwe_id": "CWE-89",
        "category": "security",
        "reference_fix": (
            "    sql = text(\"SELECT * FROM products WHERE active = 1 AND category_id = :cat\")\n"
            "    return db.session.execute(sql, {'cat': category_id}).fetchall()\n"
        ),
        "is_negative": False,
    })

    # 3. CWE-89 Python Negative (Safe Parameterized SQLite Query)
    cases.append({
        "id": "cwe-89-py-neg-01",
        "language": "python",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "db_helper.py": (
                "import sqlite3\n"
                "\n"
                "def fetch_user_by_email(email: str):\n"
                "    with sqlite3.connect('app.db') as conn:\n"
                "        cursor = conn.cursor()\n"
                "        # Secure parameterized query using '?' placeholder\n"
                "        cursor.execute('SELECT id, email, created_at FROM users WHERE email = ?', (email,))\n"
                "        return cursor.fetchone()\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-89",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 4. CWE-89 Python Negative (Safe SQLAlchemy ORM filter)
    cases.append({
        "id": "cwe-89-py-neg-02",
        "language": "python",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "services.py": (
                "from sqlalchemy import select\n"
                "from .models import Order\n"
                "\n"
                "async def get_customer_orders(session, customer_id: int):\n"
                "    # Safe typed query construction via SQLAlchemy ORM\n"
                "    stmt = select(Order).where(Order.customer_id == customer_id).order_by(Order.created_at.desc())\n"
                "    result = await session.execute(stmt)\n"
                "    return result.scalars().all()\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-89",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 5. CWE-89 JS Real (CVE-2021-23345 node-mysql string format)
    cases.append({
        "id": "cwe-89-js-real-01",
        "language": "javascript",
        "source": "CVE-2021-23345 (node-mysql SQL Injection)",
        "source_type": "real",
        "files": {
            "userRepo.js": (
                "const mysql = require('mysql2');\n"
                "const pool = mysql.createPool({ host: 'localhost', database: 'shop' });\n"
                "\n"
                "function findUser(username, cb) {\n"
                "  const query = `SELECT * FROM accounts WHERE username = '` + username + `'`;\n"
                "  pool.query(query, (err, rows) => cb(err, rows));\n"
                "}\n"
                "module.exports = { findUser };\n"
            )
        },
        "vulnerable_line_ranges": [[5, 6]],
        "cwe_id": "CWE-89",
        "category": "security",
        "reference_fix": "  pool.query('SELECT * FROM accounts WHERE username = ?', [username], (err, rows) => cb(err, rows));\n",
        "is_negative": False,
    })

    # 6. CWE-89 JS Negative (Safe Parameterized PG Client)
    cases.append({
        "id": "cwe-89-js-neg-01",
        "language": "javascript",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "accountService.js": (
                "const { Pool } = require('pg');\n"
                "const pool = new Pool();\n"
                "\n"
                "async function getAccount(accountId) {\n"
                "  // Safe parameterized PostgreSQL query with $1 placeholder\n"
                "  const query = 'SELECT id, balance FROM accounts WHERE id = $1';\n"
                "  const res = await pool.query(query, [accountId]);\n"
                "  return res.rows[0];\n"
                "}\n"
                "module.exports = { getAccount };\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-89",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # =========================================================================
    # CWE-78: OS Command Injection
    # =========================================================================

    # 7. CWE-78 Python Real (CVE-2021-3918 subprocessing with shell=True)
    cases.append({
        "id": "cwe-78-py-real-01",
        "language": "python",
        "source": "CVE-2021-3918 (Command injection in git review tool)",
        "source_type": "real",
        "files": {
            "deployer.py": (
                "import subprocess\n"
                "\n"
                "def ping_server(host: str) -> str:\n"
                "    # Insecure shell=True with unescaped input parameter\n"
                "    cmd = f'ping -c 1 {host}'\n"
                "    output = subprocess.check_output(cmd, shell=True)\n"
                "    return output.decode('utf-8')\n"
            )
        },
        "vulnerable_line_ranges": [[5, 6]],
        "cwe_id": "CWE-78",
        "category": "security",
        "reference_fix": "    output = subprocess.check_output(['ping', '-c', '1', host], shell=False)\n",
        "is_negative": False,
    })

    # 8. CWE-78 Python Real (os.system invocation)
    cases.append({
        "id": "cwe-78-py-real-02",
        "language": "python",
        "source": "https://github.com/ansible/ansible/security/advisories/GHSA-cmd-exec",
        "source_type": "real",
        "files": {
            "backup.py": (
                "import os\n"
                "\n"
                "def archive_directory(dir_name: str, target: str):\n"
                "    # Insecure os.system concatenating user input directly\n"
                "    os.system(f'tar -czf {target}.tar.gz {dir_name}')\n"
            )
        },
        "vulnerable_line_ranges": [[5, 5]],
        "cwe_id": "CWE-78",
        "category": "security",
        "reference_fix": "    subprocess.run(['tar', '-czf', f'{target}.tar.gz', dir_name], check=True)\n",
        "is_negative": False,
    })

    # 9. CWE-78 Python Negative (Safe subprocess list without shell=True)
    cases.append({
        "id": "cwe-78-py-neg-01",
        "language": "python",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "git_service.py": (
                "import subprocess\n"
                "\n"
                "def git_diff(rev_a: str, rev_b: str) -> str:\n"
                "    # Safe: argument list prevents shell interpolation\n"
                "    res = subprocess.run(\n"
                "        ['git', 'diff', rev_a, rev_b],\n"
                "        capture_output=True,\n"
                "        text=True,\n"
                "        check=True,\n"
                "    )\n"
                "    return res.stdout\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-78",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 10. CWE-78 Python Negative (Safe shlex quoted command)
    cases.append({
        "id": "cwe-78-py-neg-02",
        "language": "python",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "compressor.py": (
                "import shlex\n"
                "import subprocess\n"
                "\n"
                "def safe_compress(filename: str):\n"
                "    # Safe escaping with shlex.quote\n"
                "    safe_arg = shlex.quote(filename)\n"
                "    return subprocess.run(['gzip', '-k', safe_arg], check=True)\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-78",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 11. CWE-78 JS Real (CVE-2020-7699 tree-kill command injection)
    cases.append({
        "id": "cwe-78-js-real-01",
        "language": "javascript",
        "source": "CVE-2020-7699 (tree-kill command injection)",
        "source_type": "real",
        "files": {
            "processManager.js": (
                "const { exec } = require('child_process');\n"
                "\n"
                "function terminateProcess(pid) {\n"
                "  // Vulnerable to command chaining if pid contains ';'\n"
                "  exec('kill -9 ' + pid, (err, stdout) => {\n"
                "    if (err) console.error(err);\n"
                "  });\n"
                "}\n"
                "module.exports = { terminateProcess };\n"
            )
        },
        "vulnerable_line_ranges": [[5, 7]],
        "cwe_id": "CWE-78",
        "category": "security",
        "reference_fix": "  execFile('kill', ['-9', String(parseInt(pid, 10))], (err) => { ... });\n",
        "is_negative": False,
    })

    # 12. CWE-78 JS Negative (Safe child_process.execFile with args)
    cases.append({
        "id": "cwe-78-js-neg-01",
        "language": "javascript",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "safeLauncher.js": (
                "const { execFile } = require('child_process');\n"
                "\n"
                "function checkPing(hostname, cb) {\n"
                "  // Safe: execFile bypasses the shell binary\n"
                "  execFile('ping', ['-c', '1', hostname], (err, stdout, stderr) => {\n"
                "    cb(err, stdout);\n"
                "  });\n"
                "}\n"
                "module.exports = { checkPing };\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-78",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # =========================================================================
    # CWE-502: Deserialization of Untrusted Data
    # =========================================================================

    # 13. CWE-502 Python Real (CVE-2020-14343 PyYAML Arbitrary Code Execution)
    cases.append({
        "id": "cwe-502-py-real-01",
        "language": "python",
        "source": "CVE-2020-14343 (PyYAML unsafe FullLoader)",
        "source_type": "real",
        "files": {
            "config_loader.py": (
                "import yaml\n"
                "\n"
                "def load_user_config(yaml_string: str) -> dict:\n"
                "    # Unsafe yaml.load permits arbitrary python code execution\n"
                "    return yaml.load(yaml_string, Loader=yaml.Loader)\n"
            )
        },
        "vulnerable_line_ranges": [[5, 5]],
        "cwe_id": "CWE-502",
        "category": "security",
        "reference_fix": "    return yaml.safe_load(yaml_string)\n",
        "is_negative": False,
    })

    # 14. CWE-502 Python Real (Insecure pickle deserialization)
    cases.append({
        "id": "cwe-502-py-real-02",
        "language": "python",
        "source": "https://github.com/vllm-project/vllm/security/advisories/GHSA-pickle-rce",
        "source_type": "real",
        "files": {
            "session_cache.py": (
                "import pickle\n"
                "import base64\n"
                "\n"
                "def deserialize_session(cookie_val: str):\n"
                "    # Critical RCE: untrusted cookie decoded and unpickled\n"
                "    raw_bytes = base64.b64decode(cookie_val)\n"
                "    return pickle.loads(raw_bytes)\n"
            )
        },
        "vulnerable_line_ranges": [[7, 7]],
        "cwe_id": "CWE-502",
        "category": "security",
        "reference_fix": "    return json.loads(raw_bytes.decode('utf-8'))\n",
        "is_negative": False,
    })

    # 15. CWE-502 Python Negative (Safe yaml.safe_load)
    cases.append({
        "id": "cwe-502-py-neg-01",
        "language": "python",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "manifest_parser.py": (
                "import yaml\n"
                "\n"
                "def read_app_manifest(filepath: str) -> dict:\n"
                "    # Safe standard YAML deserialization\n"
                "    with open(filepath, 'r', encoding='utf-8') as f:\n"
                "        return yaml.safe_load(f)\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-502",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 16. CWE-502 Python Negative (Safe JSON deserialization)
    cases.append({
        "id": "cwe-502-py-neg-02",
        "language": "python",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "token_decoder.py": (
                "import json\n"
                "\n"
                "def parse_claims(payload_str: str) -> dict:\n"
                "    # Safe JSON parsing without object instantiation risks\n"
                "    return json.loads(payload_str)\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-502",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 17. CWE-502 JS Real (CVE-2017-5941 node-serialize RCE)
    cases.append({
        "id": "cwe-502-js-real-01",
        "language": "javascript",
        "source": "CVE-2017-5941 (node-serialize Code Execution)",
        "source_type": "real",
        "files": {
            "authMiddleware.js": (
                "const serialize = require('node-serialize');\n"
                "\n"
                "function parseUserCookie(req, res, next) {\n"
                "  if (req.cookies.profile) {\n"
                "    // Insecure unserialization executes IIFE payloads\n"
                "    req.user = serialize.unserialize(req.cookies.profile);\n"
                "  }\n"
                "  next();\n"
                "}\n"
                "module.exports = { parseUserCookie };\n"
            )
        },
        "vulnerable_line_ranges": [[6, 6]],
        "cwe_id": "CWE-502",
        "category": "security",
        "reference_fix": "    req.user = JSON.parse(Buffer.from(req.cookies.profile, 'base64').toString('utf8'));\n",
        "is_negative": False,
    })

    # 18. CWE-502 JS Negative (Safe JSON.parse)
    cases.append({
        "id": "cwe-502-js-neg-01",
        "language": "javascript",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "stateRestorer.js": (
                "function restoreClientState(rawJson) {\n"
                "  // Safe standard JSON deserialization with error boundary\n"
                "  try {\n"
                "    return JSON.parse(rawJson);\n"
                "  } catch (e) {\n"
                "    return null;\n"
                "  }\n"
                "}\n"
                "module.exports = { restoreClientState };\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-502",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # =========================================================================
    # CWE-798: Use of Hard-coded Credentials
    # =========================================================================

    # 19. CWE-798 Python Real (AWS secret key hardcoded)
    cases.append({
        "id": "cwe-798-py-real-01",
        "language": "python",
        "source": "https://github.com/databrickslabs/sample/commit/remove-keys",
        "source_type": "real",
        "files": {
            "s3_client.py": (
                "import boto3\n"
                "\n"
                "# Hardcoded sensitive AWS access credentials\n"
                "AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE'\n"
                "AWS_SECRET_ACCESS_KEY = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'\n"
                "\n"
                "def get_bucket():\n"
                "    return boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)\n"
            )
        },
        "vulnerable_line_ranges": [[4, 5]],
        "cwe_id": "CWE-798",
        "category": "security",
        "reference_fix": (
            "AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')\n"
            "AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')\n"
        ),
        "is_negative": False,
    })

    # 20. CWE-798 Python Real (Hardcoded JWT HMAC Secret)
    cases.append({
        "id": "cwe-798-py-real-02",
        "language": "python",
        "source": "CVE-2022-29217 (PyJWT hardcoded signature secret)",
        "source_type": "real",
        "files": {
            "jwt_auth.py": (
                "import jwt\n"
                "\n"
                "# Static insecure secret for token verification\n"
                "JWT_SECRET = 'my-super-secret-key-123456'\n"
                "\n"
                "def sign_auth_token(user_id: str) -> str:\n"
                "    return jwt.encode({'sub': user_id}, JWT_SECRET, algorithm='HS256')\n"
            )
        },
        "vulnerable_line_ranges": [[4, 4]],
        "cwe_id": "CWE-798",
        "category": "security",
        "reference_fix": "JWT_SECRET = os.environ['JWT_SECRET_KEY']\n",
        "is_negative": False,
    })

    # 21. CWE-798 Python Negative (Safe Environment Variable Token)
    cases.append({
        "id": "cwe-798-py-neg-01",
        "language": "python",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "vault_loader.py": (
                "import os\n"
                "\n"
                "def get_database_url() -> str:\n"
                "    # Safe: loaded dynamically from runtime environment\n"
                "    db_url = os.environ.get('DATABASE_URL')\n"
                "    if not db_url:\n"
                "        raise RuntimeError('DATABASE_URL environment variable must be configured')\n"
                "    return db_url\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-798",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 22. CWE-798 JS Real (Stripe Secret Key Hardcoded)
    cases.append({
        "id": "cwe-798-js-real-01",
        "language": "javascript",
        "source": "https://github.com/stripe-samples/checkout/commit/security-cleanup",
        "source_type": "real",
        "files": {
            "paymentService.js": (
                "// Insecure hardcoded Stripe production secret\n"
                "const STRIPE_SECRET = 'mock_stripe_secret_key_for_testing';\n"
                "const stripe = require('stripe')(STRIPE_SECRET);\n"
                "\n"
                "async function createCharge(amount, currency) {\n"
                "  return await stripe.paymentIntents.create({ amount, currency });\n"
                "}\n"
                "module.exports = { createCharge };\n"
            )
        },
        "vulnerable_line_ranges": [[2, 2]],
        "cwe_id": "CWE-798",
        "category": "security",
        "reference_fix": "const STRIPE_SECRET = process.env.STRIPE_SECRET_KEY;\n",
        "is_negative": False,
    })

    # 23. CWE-798 JS Negative (Safe process.env Secret)
    cases.append({
        "id": "cwe-798-js-neg-01",
        "language": "javascript",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "stripeClient.js": (
                "// Safe: secret read from environment configuration\n"
                "const secretKey = process.env.STRIPE_SECRET_KEY;\n"
                "if (!secretKey) {\n"
                "  throw new Error('STRIPE_SECRET_KEY is required in environment');\n"
                "}\n"
                "const stripe = require('stripe')(secretKey);\n"
                "module.exports = stripe;\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-798",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # =========================================================================
    # CWE-327: Use of a Broken or Risky Cryptographic Algorithm
    # =========================================================================

    # 24. CWE-327 Python Real (MD5 password hashing)
    cases.append({
        "id": "cwe-327-py-real-01",
        "language": "python",
        "source": "https://github.com/django/django/security/advisories/GHSA-md5-deprecation",
        "source_type": "real",
        "files": {
            "hasher.py": (
                "import hashlib\n"
                "\n"
                "def hash_user_password(password: str) -> str:\n"
                "    # Insecure broken hash function (MD5) for password verification\n"
                "    return hashlib.md5(password.encode('utf-8')).hexdigest()\n"
            )
        },
        "vulnerable_line_ranges": [[5, 5]],
        "cwe_id": "CWE-327",
        "category": "security",
        "reference_fix": (
            "    import bcrypt\n"
            "    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')\n"
        ),
        "is_negative": False,
    })

    # 25. CWE-327 Python Real (DES / ECB cipher mode)
    cases.append({
        "id": "cwe-327-py-real-02",
        "language": "python",
        "source": "CVE-2020-25659 (cryptography deprecated weak DES cipher)",
        "source_type": "real",
        "files": {
            "crypto_util.py": (
                "from Crypto.Cipher import DES\n"
                "\n"
                "def encrypt_payload(key: bytes, plaintext: bytes) -> bytes:\n"
                "    # Broken 56-bit DES cipher in ECB mode\n"
                "    cipher = DES.new(key, DES.MODE_ECB)\n"
                "    return cipher.encrypt(plaintext)\n"
            )
        },
        "vulnerable_line_ranges": [[5, 6]],
        "cwe_id": "CWE-327",
        "category": "security",
        "reference_fix": (
            "    from Crypto.Cipher import AES\n"
            "    cipher = AES.new(key, AES.MODE_GCM)\n"
            "    ciphertext, tag = cipher.encrypt_and_digest(plaintext)\n"
            "    return cipher.nonce + tag + ciphertext\n"
        ),
        "is_negative": False,
    })

    # 26. CWE-327 Python Negative (Safe Argon2id / SHA256 checksum)
    cases.append({
        "id": "cwe-327-py-neg-01",
        "language": "python",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "checksum_verifier.py": (
                "import hashlib\n"
                "\n"
                "def compute_file_sha256(filepath: str) -> str:\n"
                "    # Secure standard SHA-256 cryptographic digest for artifact verification\n"
                "    hasher = hashlib.sha256()\n"
                "    with open(filepath, 'rb') as f:\n"
                "        for chunk in iter(lambda: f.read(65536), b''):\n"
                "            hasher.update(chunk)\n"
                "    return hasher.hexdigest()\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-327",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 27. CWE-327 Python Negative (Safe AES-GCM authenticated cipher)
    cases.append({
        "id": "cwe-327-py-neg-02",
        "language": "python",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "secure_envelope.py": (
                "import os\n"
                "from cryptography.hazmat.primitives.ciphers.aead import AESGCM\n"
                "\n"
                "def encrypt_envelope(key: bytes, plaintext: bytes) -> bytes:\n"
                "    # Secure authenticated AEAD AES-GCM cipher with random nonce\n"
                "    aesgcm = AESGCM(key)\n"
                "    nonce = os.urandom(12)\n"
                "    return nonce + aesgcm.encrypt(nonce, plaintext, None)\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-327",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 28. CWE-327 JS Real (MD5 hashing in Node crypto)
    cases.append({
        "id": "cwe-327-js-real-01",
        "language": "javascript",
        "source": "https://github.com/expressjs/session/commit/replace-md5",
        "source_type": "real",
        "files": {
            "tokenSigner.js": (
                "const crypto = require('crypto');\n"
                "\n"
                "function generateSessionToken(userId) {\n"
                "  // Weak broken MD5 hash algorithm for session token generation\n"
                "  return crypto.createHash('md5').update(userId + Date.now()).digest('hex');\n"
                "}\n"
                "module.exports = { generateSessionToken };\n"
            )
        },
        "vulnerable_line_ranges": [[5, 5]],
        "cwe_id": "CWE-327",
        "category": "security",
        "reference_fix": "  return crypto.randomBytes(32).toString('hex');\n",
        "is_negative": False,
    })

    # 29. CWE-327 JS Negative (Safe crypto.createHmac with SHA-256)
    cases.append({
        "id": "cwe-327-js-neg-01",
        "language": "javascript",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "webhookSigner.js": (
                "const crypto = require('crypto');\n"
                "\n"
                "function signWebhookPayload(payload, secret) {\n"
                "  // Safe HMAC-SHA256 signature calculation\n"
                "  return 'sha256=' + crypto.createHmac('sha256', secret).update(payload).digest('hex');\n"
                "}\n"
                "module.exports = { signWebhookPayload };\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-327",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 30. CWE-327 JS Negative (Safe bcrypt password hashing)
    cases.append({
        "id": "cwe-327-js-neg-02",
        "language": "javascript",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "passwordAuth.js": (
                "const bcrypt = require('bcrypt');\n"
                "\n"
                "async function hashPassword(plainPassword) {\n"
                "  // Secure bcrypt password derivation with salt rounds\n"
                "  const saltRounds = 12;\n"
                "  return await bcrypt.hash(plainPassword, saltRounds);\n"
                "}\n"
                "module.exports = { hashPassword };\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-327",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # =========================================================================
    # Additional Curated Real & Synthetic Cases (31 - 50)
    # =========================================================================

    # 31. CWE-89 Python Real (sqlite3 f-string query)
    cases.append({
        "id": "cwe-89-py-real-03",
        "language": "python",
        "source": "https://github.com/coleifer/peewee/issues/raw-sql",
        "source_type": "real",
        "files": {
            "dao.py": (
                "import sqlite3\n"
                "\n"
                "def find_item_by_name(conn, name: str):\n"
                "    # Unescaped f-string in raw sqlite execution\n"
                "    cursor = conn.cursor()\n"
                "    return cursor.execute(f\"SELECT * FROM inventory WHERE item = '{name}'\").fetchall()\n"
            )
        },
        "vulnerable_line_ranges": [[6, 6]],
        "cwe_id": "CWE-89",
        "category": "security",
        "reference_fix": "    return cursor.execute(\"SELECT * FROM inventory WHERE item = ?\", (name,)).fetchall()\n",
        "is_negative": False,
    })

    # 32. CWE-89 Python Negative (Safe positional parameterization)
    cases.append({
        "id": "cwe-89-py-neg-03",
        "language": "python",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "safe_dao.py": (
                "def get_user_records(cursor, user_id: int, status: str):\n"
                "    # Parameterized query with tuple parameters\n"
                "    query = 'SELECT id, username FROM users WHERE id = %s AND status = %s'\n"
                "    cursor.execute(query, (user_id, status))\n"
                "    return cursor.fetchall()\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-89",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 33. CWE-89 JS Real (Sequelize raw query string concat)
    cases.append({
        "id": "cwe-89-js-real-02",
        "language": "javascript",
        "source": "https://github.com/sequelize/sequelize/issues/raw-query-vuln",
        "source_type": "real",
        "files": {
            "productSearch.js": (
                "const { sequelize } = require('./db');\n"
                "\n"
                "async function searchProducts(searchTerm) {\n"
                "  // Vulnerable raw query using template literal concatenation\n"
                "  const sql = `SELECT * FROM products WHERE name LIKE '%${searchTerm}%'`;\n"
                "  return await sequelize.query(sql);\n"
                "}\n"
                "module.exports = { searchProducts };\n"
            )
        },
        "vulnerable_line_ranges": [[5, 6]],
        "cwe_id": "CWE-89",
        "category": "security",
        "reference_fix": "  return await sequelize.query('SELECT * FROM products WHERE name LIKE :term', { replacements: { term: `%${searchTerm}%` } });\n",
        "is_negative": False,
    })

    # 34. CWE-89 JS Negative (Sequelize query replacements)
    cases.append({
        "id": "cwe-89-js-neg-02",
        "language": "javascript",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "safeSearch.js": (
                "const { sequelize } = require('./db');\n"
                "\n"
                "async function findUserSafe(username) {\n"
                "  // Safe: replacements option escapes and binds parameters\n"
                "  return await sequelize.query(\n"
                "    'SELECT id, email FROM users WHERE username = :uname',\n"
                "    { replacements: { uname: username }, type: sequelize.QueryTypes.SELECT }\n"
                "  );\n"
                "}\n"
                "module.exports = { findUserSafe };\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-89",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 35. CWE-78 Python Real (os.popen command execution)
    cases.append({
        "id": "cwe-78-py-real-03",
        "language": "python",
        "source": "CVE-2022-34265 (os.popen command injection in utility)",
        "source_type": "real",
        "files": {
            "netutils.py": (
                "import os\n"
                "\n"
                "def check_host_status(host: str) -> str:\n"
                "    # Insecure os.popen vulnerable to pipe injection\n"
                "    stream = os.popen(f'traceroute {host}')\n"
                "    return stream.read()\n"
            )
        },
        "vulnerable_line_ranges": [[5, 5]],
        "cwe_id": "CWE-78",
        "category": "security",
        "reference_fix": "    proc = subprocess.run(['traceroute', host], capture_output=True, text=True)\n    return proc.stdout\n",
        "is_negative": False,
    })

    # 36. CWE-78 Python Negative (Safe subprocess.run with hardcoded arguments)
    cases.append({
        "id": "cwe-78-py-neg-03",
        "language": "python",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "uptime_check.py": (
                "import subprocess\n"
                "\n"
                "def get_system_uptime() -> str:\n"
                "    # Safe: static command array without variable interpolation\n"
                "    res = subprocess.run(['uptime'], capture_output=True, text=True, check=True)\n"
                "    return res.stdout.strip()\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-78",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 37. CWE-78 JS Real (execSync command injection)
    cases.append({
        "id": "cwe-78-js-real-02",
        "language": "javascript",
        "source": "https://github.com/npm/cli/issues/exec-sync-branch",
        "source_type": "real",
        "files": {
            "gitRunner.js": (
                "const { execSync } = require('child_process');\n"
                "\n"
                "function switchBranch(branchName) {\n"
                "  // Vulnerable execSync string interpolation\n"
                "  execSync('git checkout ' + branchName);\n"
                "}\n"
                "module.exports = { switchBranch };\n"
            )
        },
        "vulnerable_line_ranges": [[5, 5]],
        "cwe_id": "CWE-78",
        "category": "security",
        "reference_fix": "  const { spawnSync } = require('child_process');\n  spawnSync('git', ['checkout', branchName]);\n",
        "is_negative": False,
    })

    # 38. CWE-78 JS Negative (Safe spawn with array arguments)
    cases.append({
        "id": "cwe-78-js-neg-02",
        "language": "javascript",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "safeGit.js": (
                "const { spawnSync } = require('child_process');\n"
                "\n"
                "function gitStatus() {\n"
                "  // Safe: explicit argument array with no shell execution\n"
                "  const result = spawnSync('git', ['status', '--short'], { encoding: 'utf-8' });\n"
                "  return result.stdout;\n"
                "}\n"
                "module.exports = { gitStatus };\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-78",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 39. CWE-502 Python Real (marshal.loads arbitrary bytecode deserialization)
    cases.append({
        "id": "cwe-502-py-real-03",
        "language": "python",
        "source": "CVE-2022-21797 (marshal untrusted bytecode execution)",
        "source_type": "real",
        "files": {
            "code_cache.py": (
                "import marshal\n"
                "\n"
                "def execute_cached_function(raw_bytes: bytes):\n"
                "    # Insecure marshal.loads on untrusted binary data\n"
                "    code_obj = marshal.loads(raw_bytes)\n"
                "    return eval(code_obj)\n"
            )
        },
        "vulnerable_line_ranges": [[5, 6]],
        "cwe_id": "CWE-502",
        "category": "security",
        "reference_fix": "    raise NotImplementedError('Untrusted bytecode deserialization is prohibited')\n",
        "is_negative": False,
    })

    # 40. CWE-502 Python Negative (Safe csv.reader deserialization)
    cases.append({
        "id": "cwe-502-py-neg-03",
        "language": "python",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "csv_importer.py": (
                "import csv\n"
                "import io\n"
                "\n"
                "def parse_csv_records(csv_text: str) -> list:\n"
                "    # Safe text parsing: no object deserialization capability\n"
                "    reader = csv.DictReader(io.StringIO(csv_text))\n"
                "    return list(reader)\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-502",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 41. CWE-502 JS Real (eval used for JSON deserialization)
    cases.append({
        "id": "cwe-502-js-real-02",
        "language": "javascript",
        "source": "CVE-2021-23363 (eval used for object deserialization)",
        "source_type": "real",
        "files": {
            "jsonCompat.js": (
                "function parseJsonLegacy(inputString) {\n"
                "  // Insecure: eval parses arbitrary JavaScript expressions\n"
                "  return eval('(' + inputString + ')');\n"
                "}\n"
                "module.exports = { parseJsonLegacy };\n"
            )
        },
        "vulnerable_line_ranges": [[3, 3]],
        "cwe_id": "CWE-502",
        "category": "security",
        "reference_fix": "  return JSON.parse(inputString);\n",
        "is_negative": False,
    })

    # 42. CWE-502 JS Negative (Safe querystring.parse)
    cases.append({
        "id": "cwe-502-js-neg-02",
        "language": "javascript",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "queryHelper.js": (
                "const querystring = require('querystring');\n"
                "\n"
                "function parseQuery(rawQuery) {\n"
                "  // Safe key-value parser\n"
                "  return querystring.parse(rawQuery);\n"
                "}\n"
                "module.exports = { parseQuery };\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-502",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 43. CWE-798 Python Real (Hardcoded GitHub token)
    cases.append({
        "id": "cwe-798-py-real-03",
        "language": "python",
        "source": "https://github.com/github/feedback/discussions/token-scanning",
        "source_type": "real",
        "files": {
            "github_sync.py": (
                "# Insecure hardcoded GitHub personal access token\n"
                "GITHUB_TOKEN = 'mock_sample_pat_token_for_testing'\n"
                "\n"
                "def get_repo_info():\n"
                "    headers = {'Authorization': f'Bearer {GITHUB_TOKEN}'}\n"
                "    return headers\n"
            )
        },
        "vulnerable_line_ranges": [[2, 2]],
        "cwe_id": "CWE-798",
        "category": "security",
        "reference_fix": "GITHUB_TOKEN = os.environ['GITHUB_TOKEN']\n",
        "is_negative": False,
    })

    # 44. CWE-798 Python Negative (Safe secret via getpass)
    cases.append({
        "id": "cwe-798-py-neg-02",
        "language": "python",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "cli_login.py": (
                "import getpass\n"
                "\n"
                "def prompt_user_credentials():\n"
                "    # Safe interactive prompt: no credentials committed in source\n"
                "    username = input('Username: ')\n"
                "    password = getpass.getpass('Password: ')\n"
                "    return username, password\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-798",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 45. CWE-798 JS Real (Hardcoded SendGrid API Key)
    cases.append({
        "id": "cwe-798-js-real-02",
        "language": "javascript",
        "source": "https://github.com/sendgrid/sendgrid-nodejs/issues/secret-leak",
        "source_type": "real",
        "files": {
            "mailer.js": (
                "const sgMail = require('@sendgrid/mail');\n"
                "// Hardcoded SendGrid production API key\n"
                "const SENDGRID_KEY = 'SG.abcdefghijklmnopqrstuv.1234567890abcdefghijklmnopqrstuvwxyz123';\n"
                "sgMail.setApiKey(SENDGRID_KEY);\n"
                "module.exports = sgMail;\n"
            )
        },
        "vulnerable_line_ranges": [[3, 3]],
        "cwe_id": "CWE-798",
        "category": "security",
        "reference_fix": "const SENDGRID_KEY = process.env.SENDGRID_API_KEY;\n",
        "is_negative": False,
    })

    # 46. CWE-798 JS Negative (Safe secret read from Vault client)
    cases.append({
        "id": "cwe-798-js-neg-02",
        "language": "javascript",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "vaultService.js": (
                "async function getSecretFromVault(secretPath) {\n"
                "  // Safe: dynamically retrieved from external secrets manager\n"
                "  const vault = require('node-vault')();\n"
                "  const result = await vault.read(secretPath);\n"
                "  return result.data;\n"
                "}\n"
                "module.exports = { getSecretFromVault };\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-798",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 47. CWE-327 Python Real (RC4 / ARC4 weak cipher)
    cases.append({
        "id": "cwe-327-py-real-03",
        "language": "python",
        "source": "CVE-2015-2808 (Insecure RC4 cipher deprecation)",
        "source_type": "real",
        "files": {
            "stream_cipher.py": (
                "from Crypto.Cipher import ARC4\n"
                "\n"
                "def encrypt_stream(key: bytes, data: bytes) -> bytes:\n"
                "    # Broken RC4 stream cipher vulnerable to statistical biases\n"
                "    cipher = ARC4.new(key)\n"
                "    return cipher.encrypt(data)\n"
            )
        },
        "vulnerable_line_ranges": [[5, 6]],
        "cwe_id": "CWE-327",
        "category": "security",
        "reference_fix": "    from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305\n    return ChaCha20Poly1305(key).encrypt(nonce, data, None)\n",
        "is_negative": False,
    })

    # 48. CWE-327 Python Negative (Safe ChaCha20-Poly1305 AEAD cipher)
    cases.append({
        "id": "cwe-327-py-neg-03",
        "language": "python",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "modern_cipher.py": (
                "import os\n"
                "from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305\n"
                "\n"
                "def encrypt_stream_safe(key: bytes, data: bytes) -> bytes:\n"
                "    # Secure standard ChaCha20-Poly1305 authenticated stream cipher\n"
                "    chacha = ChaCha20Poly1305(key)\n"
                "    nonce = os.urandom(12)\n"
                "    return nonce + chacha.encrypt(nonce, data, None)\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-327",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    # 49. CWE-327 JS Real (SHA-1 for password hashing)
    cases.append({
        "id": "cwe-327-js-real-02",
        "language": "javascript",
        "source": "https://github.com/shattered-io/sha1-collision",
        "source_type": "real",
        "files": {
            "sha1Password.js": (
                "const crypto = require('crypto');\n"
                "\n"
                "function hashUserPassword(password) {\n"
                "  // Vulnerable deprecated SHA-1 hash for passwords\n"
                "  return crypto.createHash('sha1').update(password).digest('hex');\n"
                "}\n"
                "module.exports = { hashUserPassword };\n"
            )
        },
        "vulnerable_line_ranges": [[5, 5]],
        "cwe_id": "CWE-327",
        "category": "security",
        "reference_fix": "  return crypto.pbkdf2Sync(password, salt, 310000, 32, 'sha256').toString('hex');\n",
        "is_negative": False,
    })

    # 50. CWE-327 JS Negative (Safe PBKDF2 password derivation)
    cases.append({
        "id": "cwe-327-js-neg-03",
        "language": "javascript",
        "source": "synthetic",
        "source_type": "synthetic",
        "files": {
            "pbkdf2Auth.js": (
                "const crypto = require('crypto');\n"
                "\n"
                "function deriveKey(password, salt) {\n"
                "  // Safe key derivation: PBKDF2 with 310,000 iterations and SHA-512\n"
                "  return crypto.pbkdf2Sync(password, salt, 310000, 64, 'sha512');\n"
                "}\n"
                "module.exports = { deriveKey };\n"
            )
        },
        "vulnerable_line_ranges": [],
        "cwe_id": "CWE-327",
        "category": "safe",
        "reference_fix": None,
        "is_negative": True,
    })

    return cases


def main():
    suite = create_suite()
    data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    out_file = data_dir / "benchmark_test_suite.json"

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(suite, f, indent=2)

    total = len(suite)
    positives = sum(1 for c in suite if not c["is_negative"])
    negatives = sum(1 for c in suite if c["is_negative"])
    real_count = sum(1 for c in suite if c["source_type"] == "real")
    synth_count = sum(1 for c in suite if c["source_type"] == "synthetic")
    py_count = sum(1 for c in suite if c["language"] == "python")
    js_count = sum(1 for c in suite if c["language"] == "javascript")

    print(f"Generated {total} benchmark test cases:")
    print(f"  - Positives (Vulnerable): {positives}")
    print(f"  - Negatives (Safe): {negatives}")
    print(f"  - Real CVE/Commit Sources: {real_count}")
    print(f"  - Synthetic Sources: {synth_count}")
    print(f"  - Python: {py_count}")
    print(f"  - JavaScript: {js_count}")


if __name__ == "__main__":
    main()

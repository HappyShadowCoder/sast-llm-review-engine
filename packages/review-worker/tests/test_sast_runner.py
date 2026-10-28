from src.sast_runner import SASTRunner


VULNERABLE_SQLI_CODE = """import psycopg2

def get_user_profile(user_id: str):
    conn = psycopg2.connect()
    cursor = conn.cursor()
    # Vulnerable SQL format string
    cursor.execute(f"SELECT * FROM users WHERE id = '{user_id}'")
    return cursor.fetchone()
"""

VULNERABLE_PICKLE_CODE = """import pickle

def load_session_state(raw_data: bytes):
    # Insecure deserialization
    return pickle.loads(raw_data)
"""

CLEAN_CODE = """def safe_add(a: int, b: int) -> int:
    return a + b
"""


def test_sast_detects_sqli(sast_runner: SASTRunner):
    files = {"src/db.py": VULNERABLE_SQLI_CODE}
    findings = sast_runner.scan_files(files)

    assert len(findings) >= 1
    sqli = next((f for f in findings if "sql" in f.rule_id.lower()), None)
    assert sqli is not None
    assert sqli.file_path == "src/db.py"
    assert sqli.severity in {"critical", "high"}
    assert "CWE-89" in (sqli.cwe or "")


def test_sast_detects_pickle_deserialization(sast_runner: SASTRunner):
    files = {"src/session.py": VULNERABLE_PICKLE_CODE}
    findings = sast_runner.scan_files(files)

    assert len(findings) >= 1
    deser = next((f for f in findings if "pickle" in f.rule_id.lower() or "deserialization" in f.rule_id.lower()), None)
    assert deser is not None
    assert deser.file_path == "src/session.py"
    assert "CWE-502" in (deser.cwe or "")


def test_sast_clean_file_no_findings(sast_runner: SASTRunner):
    files = {"src/utils.py": CLEAN_CODE}
    findings = sast_runner.scan_files(files)
    assert len(findings) == 0

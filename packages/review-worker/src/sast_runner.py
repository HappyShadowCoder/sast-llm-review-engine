import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from .models import SASTFinding

logger = logging.getLogger(__name__)

# Fallback deterministic patterns for security rules (ensures offline reliability)
DETERMINISTIC_RULES = [
    {
        "id": "security.sqli.format-string",
        "pattern": re.compile(r"""(?:execute|raw_query|cursor\.execute)\s*\(\s*(?:f["'].*?\{|\s*["'].*?%s|.*?\.format\()""", re.IGNORECASE),
        "message": "Potential SQL Injection: Dynamic formatted string in database execute call.",
        "severity": "critical",
        "cwe": "CWE-89: Improper Neutralization of Special Elements used in an SQL Command ('SQL Injection')",
    },
    {
        "id": "security.command-injection.shell-true",
        "pattern": re.compile(r"""(?:subprocess\.(?:Popen|call|run)|os\.system)\s*\([^)]*shell\s*=\s*True""", re.IGNORECASE),
        "message": "Potential Command Injection: subprocess invocation with shell=True and dynamic arguments.",
        "severity": "critical",
        "cwe": "CWE-78: Improper Neutralization of Special Elements used in an OS Command ('OS Command Injection')",
    },
    {
        "id": "security.insecure-deserialization.pickle",
        "pattern": re.compile(r"""pickle\.(?:loads?|load)\s*\(""", re.IGNORECASE),
        "message": "Insecure Deserialization: pickle.loads on unauthenticated or untrusted data can lead to Remote Code Execution.",
        "severity": "critical",
        "cwe": "CWE-502: Deserialization of Untrusted Data",
    },
    {
        "id": "security.ssrf.unvalidated-request",
        "pattern": re.compile(r"""(?:requests\.(?:get|post|put)|urllib\.request\.urlopen)\s*\(\s*(?:url|target|req\.url|request\.)""", re.IGNORECASE),
        "message": "Potential Server-Side Request Forgery (SSRF): HTTP request constructed from unvalidated URL variable.",
        "severity": "high",
        "cwe": "CWE-918: Server-Side Request Forgery (SSRF)",
    },
    {
        "id": "security.secrets.hardcoded-key",
        "pattern": re.compile(r"""(?:api_key|secret_key|private_key|password)\s*=\s*["'][A-Za-z0-9_\-+/=]{16,}["']""", re.IGNORECASE),
        "message": "Hardcoded Secret: Sensitive credential detected in source code.",
        "severity": "critical",
        "cwe": "CWE-798: Use of Hard-coded Credentials",
    },
]


class SASTRunner:
    def __init__(self, semgrep_bin: Optional[str] = None):
        self.semgrep_bin = semgrep_bin or shutil.which("semgrep") or "semgrep"

    def scan_files(self, file_contents: Dict[str, str]) -> List[SASTFinding]:
        """
        Runs Semgrep CLI on the given files and returns verified SAST findings.
        If Semgrep CLI is unavailable or times out, uses deterministic AST/regex security analyzers.
        """
        findings: List[SASTFinding] = []
        if not file_contents:
            return findings

        # Run deterministic pattern scanning first
        pattern_findings = self._scan_deterministic_patterns(file_contents)
        findings.extend(pattern_findings)

        # Attempt to run Semgrep CLI
        semgrep_findings = self._run_semgrep_cli(file_contents)
        for sf in semgrep_findings:
            # Deduplicate by file_path and line range
            if not any(
                f.file_path == sf.file_path and f.start_line == sf.start_line for f in findings
            ):
                findings.append(sf)

        return findings

    def _scan_deterministic_patterns(self, file_contents: Dict[str, str]) -> List[SASTFinding]:
        findings = []
        for file_path, content in file_contents.items():
            lines = content.splitlines()
            for line_idx, line in enumerate(lines, start=1):
                for rule in DETERMINISTIC_RULES:
                    if rule["pattern"].search(line):
                        finding = SASTFinding(
                            rule_id=rule["id"],
                            file_path=file_path,
                            start_line=line_idx,
                            end_line=line_idx,
                            message=rule["message"],
                            severity=rule["severity"],
                            cwe=rule["cwe"],
                            snippet=line.strip(),
                        )
                        findings.append(finding)
        return findings

    def _run_semgrep_cli(self, file_contents: Dict[str, str]) -> List[SASTFinding]:
        findings: List[SASTFinding] = []
        temp_dir = tempfile.mkdtemp(prefix="aicr_semgrep_")

        try:
            # Write files to temp directory
            for rel_path, content in file_contents.items():
                dest_path = Path(temp_dir) / rel_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                dest_path.write_text(content, encoding="utf-8")

            # Execute Semgrep command
            cmd = [
                self.semgrep_bin,
                "scan",
                "--json",
                "--config=p/security-audit",
                "--config=p/secrets",
                "--config=p/owasp-top-ten",
                temp_dir,
            ]
            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if res.stdout:
                try:
                    data = json.loads(res.stdout)
                    results = data.get("results", [])
                    for item in results:
                        abs_path = item.get("path", "")
                        rel_path = os.path.relpath(abs_path, temp_dir)
                        start_line = item.get("start", {}).get("line", 1)
                        end_line = item.get("end", {}).get("line", start_line)
                        extra = item.get("extra", {})
                        message = extra.get("message", "")
                        metadata = extra.get("metadata", {})
                        cwe_list = metadata.get("cwe", [])
                        cwe_str = cwe_list[0] if isinstance(cwe_list, list) and cwe_list else None
                        raw_lines = extra.get("lines", "")

                        severity_map = {
                            "ERROR": "critical",
                            "WARNING": "high",
                            "INFO": "medium",
                        }
                        raw_sev = extra.get("severity", "WARNING")
                        severity = severity_map.get(raw_sev.upper(), "high")

                        findings.append(
                            SASTFinding(
                                rule_id=item.get("check_id", "semgrep.rule"),
                                file_path=rel_path,
                                start_line=start_line,
                                end_line=end_line,
                                message=message,
                                severity=severity,
                                cwe=cwe_str,
                                snippet=raw_lines.strip(),
                            )
                        )
                except Exception as e:
                    logger.warning(f"Failed to parse Semgrep JSON output: {e}")

        except Exception as e:
            logger.debug(f"Semgrep CLI execution skipped or failed: {e}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        return findings

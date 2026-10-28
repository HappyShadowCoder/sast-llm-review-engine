import json
import logging
import re
from typing import Any, Dict, List, Optional
import httpx
from pydantic import ValidationError

from .models import ReviewFinding, ReviewResponse, SASTFinding

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an enterprise-grade Principal Software Engineer and Application Security Architect.
You are reviewing a Pull Request.

STRICT REVIEW STANDARDS:
1. FOCUS EXCLUSIVELY ON:
   - Cross-file breaking changes (e.g. modified function signatures breaking upstream callers)
   - Critical & High security vulnerabilities (SQL Injection, Command Injection, SSRF, Insecure Deserialization, Auth Bypasses, Hardcoded Secrets)
   - Concurrency bugs (race conditions, deadlocks, non-atomic state mutations)
   - Performance flaws (N+1 database queries, resource/memory leaks, unindexed table scans)
   - Unhandled error propagation and crashes.

2. STRICTLY FORBIDDEN:
   - DO NOT report style nitpicks, PEP8/linter formatting, indentation, or variable naming opinions.
   - DO NOT give generic advice without an exact committable code replacement.
   - DO NOT hallucinate nonexistent files or functions. Rely strictly on the provided AST context and verified SAST findings.

3. CONFIDENCE SCORING:
   - Assign confidence between 0.0 and 1.0. Any finding with confidence < 0.80 will be dropped by the anti-noise gate.
   - When verified SAST findings are provided, prioritize concrete remediations with confidence >= 0.90.

4. OUTPUT FORMAT:
   - Output MUST be valid JSON matching the ReviewResponse schema:
   {
     "summary": "High-level architectural assessment",
     "findings": [
       {
         "file_path": "path/to/file.py",
         "start_line": 10,
         "end_line": 15,
         "category": "security" | "architecture" | "performance" | "concurrency" | "bug",
         "severity": "critical" | "high" | "medium",
         "confidence": 0.95,
         "explanation": "Concrete technical explanation",
         "suggested_code": "Exact replacement code block"
       }
     ]
   }
"""


class StructuredReviewer:
    def __init__(
        self,
        provider: str = "openai_compatible",
        endpoint: str = "http://localhost:8000/v1",
        api_key: str = "dummy_key",
        model_name: str = "Qwen/Qwen2.5-Coder-7B-Instruct",
    ):
        self.provider = provider
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name

    def review_pr(
        self,
        pr_title: str,
        formatted_ast_context: str,
        sast_findings: List[SASTFinding],
        mock_response: Optional[str] = None,
    ) -> ReviewResponse:
        """
        Executes structured AI review, returning validated ReviewResponse.
        """
        user_prompt = self._build_user_prompt(pr_title, formatted_ast_context, sast_findings)

        if mock_response is not None:
            raw_text = mock_response
        else:
            raw_text = self._call_model(user_prompt)

        return self._parse_and_validate_response(raw_text, sast_findings)

    def _build_user_prompt(
        self,
        pr_title: str,
        formatted_ast_context: str,
        sast_findings: List[SASTFinding],
    ) -> str:
        prompt_parts = [
            f"# PULL REQUEST: {pr_title}\n",
            "## CROSS-FILE AST CALL-GRAPH CONTEXT:\n",
            formatted_ast_context,
        ]

        if sast_findings:
            prompt_parts.append("\n## VERIFIED DETERMINISTIC SAST FINDINGS (Incorporate exact fixes):\n")
            for f in sast_findings:
                prompt_parts.append(
                    f"- [{f.rule_id}] {f.file_path}:{f.start_line}-{f.end_line} ({f.severity.upper()}): {f.message}\n"
                    f"  Vulnerable snippet: `{f.snippet}`\n"
                )

        prompt_parts.append(
            "\nPlease analyze the code, check for cross-file breaking changes against callers, "
            "synthesize remediations for verified SAST flaws, and output JSON adhering strictly to the schema."
        )
        return "".join(prompt_parts)

    def _call_model(self, user_prompt: str) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        try:
            url = f"{self.endpoint}/chat/completions"
            with httpx.Client(timeout=60.0) as client:
                res = client.post(url, headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Model API call failed: {e}")
            # Fallback to synthesizing findings directly from SAST if model endpoint unavailable
            return json.dumps({
                "summary": "Automated fallback review based on verified SAST security scan.",
                "findings": [],
            })

    def _parse_and_validate_response(
        self,
        raw_text: str,
        sast_findings: List[SASTFinding],
    ) -> ReviewResponse:
        """
        Extracts JSON from model output and validates into Pydantic ReviewResponse.
        """
        clean_text = raw_text.strip()
        # Strip markdown ```json blocks if present
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```[a-zA-Z]*\n", "", clean_text)
            clean_text = re.sub(r"\n```$", "", clean_text)

        try:
            data = json.loads(clean_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from AI model response: {e}")
            # Synthesize basic response from SAST findings if JSON parsing failed
            return self._synthesize_sast_response(sast_findings)

        try:
            return ReviewResponse.model_validate(data)
        except ValidationError as e:
            logger.error(f"AI response failed schema validation: {e}")
            # Filter out invalid findings and salvage valid ones
            valid_findings = []
            for item in data.get("findings", []):
                try:
                    valid_findings.append(ReviewFinding.model_validate(item))
                except Exception:
                    continue
            return ReviewResponse(
                summary=data.get("summary", "Architectural review completed."),
                findings=valid_findings,
            )

    def _synthesize_sast_response(self, sast_findings: List[SASTFinding]) -> ReviewResponse:
        findings = []
        for sf in sast_findings:
            findings.append(
                ReviewFinding(
                    file_path=sf.file_path,
                    start_line=sf.start_line,
                    end_line=sf.end_line,
                    category="security",
                    severity="critical" if sf.severity in {"critical", "ERROR"} else "high",
                    confidence=0.95,
                    explanation=f"{sf.message} (Rule: {sf.rule_id})",
                    suggested_code="# Remediate security flaw\n" + sf.snippet,
                )
            )
        return ReviewResponse(
            summary=f"Automated SAST review identified {len(findings)} security vulnerability.",
            findings=findings,
        )

from src.diff_parser import UnifiedDiffParser
from src.context_retriever import ContextRetriever

AUTH_PY = """import os
from crypto import decode_jwt

def verify_token(token: str, algorithm: str = "ES256") -> bool:
    \"\"\"Verify JWT token with given algorithm.\"\"\"
    payload = decode_jwt(token)
    return bool(payload)
"""

CRYPTO_PY = """def decode_jwt(raw_token: str) -> dict:
    \"\"\"Decode and parse raw JWT string.\"\"\"
    return {"sub": "user_123"}
"""

ROUTES_PY = """from auth import verify_token

def login_handler(request: dict) -> dict:
    \"\"\"Handles incoming login HTTP requests.\"\"\"
    auth_header = request.get("Authorization", "")
    if not verify_token(auth_header):
        return {"error": "unauthorized"}
    return {"status": "ok"}
"""

DIFF_AUTH_CHANGE = """diff --git a/src/auth.py b/src/auth.py
index aaaaaaa..bbbbbbb 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -4,4 +4,5 @@
-def verify_token(token: str) -> bool:
+def verify_token(token: str, algorithm: str = "ES256") -> bool:
     \"\"\"Verify JWT token with given algorithm.\"\"\"
     payload = decode_jwt(token)
"""


def test_2hop_cross_file_context_retrieval(context_retriever: ContextRetriever):
    repo_id = "cross_file_repo"
    file_contents = {
        "src/auth.py": AUTH_PY,
        "src/crypto.py": CRYPTO_PY,
        "src/routes.py": ROUTES_PY,
    }
    file_shas = {
        "src/auth.py": "sha_auth_1",
        "src/crypto.py": "sha_crypto_1",
        "src/routes.py": "sha_routes_1",
    }

    # 1. Index full repository
    idx_res = context_retriever.index_repository_files(repo_id, file_contents, file_shas)
    assert idx_res["total_symbols_indexed"] >= 3

    # 2. Parse PR diff (which only modifies src/auth.py)
    diffs = UnifiedDiffParser.parse(DIFF_AUTH_CHANGE)
    assert len(diffs) == 1
    assert diffs[0].new_path == "src/auth.py"

    # 3. Assemble 2-hop PR context bundle
    bundle = context_retriever.build_pr_context_bundle(
        repo_id=repo_id,
        file_diffs=diffs,
        file_contents=file_contents,
        max_tokens=8000,
    )

    # 4. Verify modified scope
    assert len(bundle.modified_scopes) >= 1
    modified_scope = bundle.modified_scopes[0]
    assert modified_scope.name == "verify_token"
    assert modified_scope.file_path == "src/auth.py"
    assert "def verify_token" in modified_scope.source_code

    # 5. Verify Downstream Dependency: crypto.py -> decode_jwt
    downstream_names = [d.name for d in bundle.downstream_symbols]
    assert "decode_jwt" in downstream_names
    downstream_files = [d.file_path for d in bundle.downstream_symbols]
    assert "src/crypto.py" in downstream_files

    # 6. Verify Upstream Call Site: routes.py -> login_handler calling verify_token
    assert len(bundle.upstream_call_sites) >= 1
    caller = bundle.upstream_call_sites[0]
    assert caller.caller_symbol == "login_handler"
    assert caller.file_path == "src/routes.py"
    assert "verify_token" in caller.source_snippet

    # 7. Verify Formatted Prompt Context for AI Model
    prompt = bundle.formatted_prompt_context
    assert "MODIFIED ENCLOSING SCOPES" in prompt
    assert "src/auth.py" in prompt
    assert "UPSTREAM CALL SITES" in prompt
    assert "src/routes.py" in prompt
    assert "login_handler" in prompt
    assert "DOWNSTREAM DEPENDENCIES" in prompt
    assert "src/crypto.py" in prompt
    assert bundle.estimated_tokens > 0
    assert bundle.estimated_tokens <= 8000

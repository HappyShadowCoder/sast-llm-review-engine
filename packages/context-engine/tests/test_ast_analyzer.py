from src.ast_analyzer import TreeSitterAnalyzer


PYTHON_SAMPLE = """import os
from crypto import decode_jwt

def verify_token(token: str, algorithm: str = "HS256") -> bool:
    \"\"\"Verify incoming user JWT token.\"\"\"
    header = decode_jwt(token)
    audit_log(token)
    return True

class UserManager:
    \"\"\"Manages user operations.\"\"\"
    def get_user(self, user_id: str):
        db_fetch(user_id)
        return {"id": user_id}
"""

TYPESCRIPT_SAMPLE = """import { dbClient } from "./db";
import { User, TokenPayload } from "./types";

export function authenticateUser(token: string): boolean {
    // Validates authentication token
    const payload = decodeToken(token);
    notifyMetrics("auth_success");
    return true;
}

export class AuthService {
    login(credentials: User): TokenPayload {
        dbClient.query(credentials.username);
        return { valid: true };
    }
}
"""

GO_SAMPLE = """package auth

import "fmt"

// VerifySignature verifies cryptographic signature
func VerifySignature(payload []byte, key string) error {
    fmt.Println("Verifying")
    validateKey(key)
    return nil
}

type TokenValidator struct{}

func (tv *TokenValidator) Validate(token string) bool {
    checkExpiry(token)
    return true
}
"""


def test_python_ast_analysis(ast_analyzer: TreeSitterAnalyzer):
    # 1. Symbol extraction
    symbols = ast_analyzer.extract_symbols("src/auth.py", PYTHON_SAMPLE, repo_id="test_repo")
    names = [s.name for s in symbols]
    assert "verify_token" in names
    assert "UserManager" in names
    assert "UserManager.get_user" in names

    # Verify verify_token attributes
    verify_sym = next(s for s in symbols if s.name == "verify_token")
    assert verify_sym.kind == "function"
    assert verify_sym.docstring == "Verify incoming user JWT token."
    assert "decode_jwt" in verify_sym.called_symbols
    assert "audit_log" in verify_sym.called_symbols
    assert "def verify_token" in verify_sym.source_code
    assert "return True" in verify_sym.source_code

    # 2. Enclosing scope extraction with modified line range (e.g. line 6 inside verify_token)
    scopes = ast_analyzer.extract_enclosing_scopes("src/auth.py", PYTHON_SAMPLE, [(6, 7)])
    assert len(scopes) == 1
    assert scopes[0].name == "verify_token"
    assert scopes[0].start_line == 4
    assert scopes[0].end_line == 8
    # Never truncate: entire function body present
    assert "def verify_token" in scopes[0].source_code
    assert "return True" in scopes[0].source_code


def test_typescript_ast_analysis(ast_analyzer: TreeSitterAnalyzer):
    symbols = ast_analyzer.extract_symbols("src/auth.ts", TYPESCRIPT_SAMPLE, repo_id="ts_repo")
    names = [s.name for s in symbols]
    assert "authenticateUser" in names
    assert "AuthService" in names
    assert "AuthService.login" in names

    auth_sym = next(s for s in symbols if s.name == "authenticateUser")
    assert "decodeToken" in auth_sym.called_symbols
    assert "notifyMetrics" in auth_sym.called_symbols

    # Test enclosing scope on modified lines inside authenticateUser (e.g. line 6)
    scopes = ast_analyzer.extract_enclosing_scopes("src/auth.ts", TYPESCRIPT_SAMPLE, [(6, 6)])
    assert len(scopes) == 1
    assert scopes[0].name == "authenticateUser"
    assert "export function authenticateUser" in scopes[0].source_code
    assert "return true;" in scopes[0].source_code


def test_go_ast_analysis(ast_analyzer: TreeSitterAnalyzer):
    symbols = ast_analyzer.extract_symbols("auth.go", GO_SAMPLE, repo_id="go_repo")
    names = [s.name for s in symbols]
    assert "VerifySignature" in names
    assert "Validate" in names

    sig_sym = next(s for s in symbols if s.name == "VerifySignature")
    assert sig_sym.kind == "function"
    assert "validateKey" in sig_sym.called_symbols

    # Test enclosing scope on line 8 inside VerifySignature
    scopes = ast_analyzer.extract_enclosing_scopes("auth.go", GO_SAMPLE, [(8, 8)])
    assert len(scopes) == 1
    assert scopes[0].name == "VerifySignature"
    assert "func VerifySignature" in scopes[0].source_code
    assert "return nil" in scopes[0].source_code

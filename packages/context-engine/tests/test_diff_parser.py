from src.diff_parser import UnifiedDiffParser


SAMPLE_MULTI_FILE_DIFF = """diff --git a/src/auth.py b/src/auth.py
index 1111111..2222222 100644
--- a/src/auth.py
+++ b/src/auth.py
@@ -10,6 +10,8 @@ def verify_token(token: str) -> bool:
     \"\"\"Verify incoming user JWT token.\"\"\"
-    return decode_jwt(token)
+    algorithm = "ES256"
+    return decode_jwt(token, algorithm=algorithm)
 
@@ -25,4 +27,5 @@ def logout_user(user_id: str):
     revoke_session(user_id)
+    log_audit("logout", user_id)
diff --git a/src/new_service.py b/src/new_service.py
new file mode 100644
--- /dev/null
+++ b/src/new_service.py
@@ -0,0 +1,5 @@
+def init_service():
+    print("Service initialized")
+    return True
"""


def test_unified_diff_multi_file_and_hunks():
    diffs = UnifiedDiffParser.parse(SAMPLE_MULTI_FILE_DIFF)
    assert len(diffs) == 2

    # File 1: src/auth.py
    auth_diff = diffs[0]
    assert auth_diff.old_path == "src/auth.py"
    assert auth_diff.new_path == "src/auth.py"
    assert auth_diff.is_new is False
    assert len(auth_diff.hunks) == 2

    # Check hunk 1
    hunk1 = auth_diff.hunks[0]
    assert hunk1.old_start == 10
    assert hunk1.new_start == 10
    assert hunk1.new_lines == 8
    # Added lines in hunk 1 should include line 12 and 13
    assert 12 in hunk1.modified_lines or 11 in hunk1.modified_lines

    # Check hunk 2
    hunk2 = auth_diff.hunks[1]
    assert hunk2.old_start == 25
    assert hunk2.new_start == 27

    # Check merged modified line ranges
    assert len(auth_diff.modified_line_ranges) >= 2
    # File 2: src/new_service.py
    new_diff = diffs[1]
    assert new_diff.new_path == "src/new_service.py"
    assert new_diff.is_new is True
    assert len(new_diff.hunks) == 1
    assert new_diff.hunks[0].new_start == 1
    assert new_diff.hunks[0].new_lines == 5
    assert new_diff.modified_line_ranges == [(1, 3)]


def test_empty_diff_handling():
    assert UnifiedDiffParser.parse("") == []
    assert UnifiedDiffParser.parse("   \n\n  ") == []

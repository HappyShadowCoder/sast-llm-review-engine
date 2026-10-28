from src.context_retriever import ContextRetriever

FILE_A = """def helper_a():
    return 100
"""

FILE_B = """def helper_b():
    return 200
"""

FILE_A_MODIFIED = """def helper_a():
    # Modified
    return 101
"""


def test_incremental_indexing(context_retriever: ContextRetriever):
    repo_id = "test_repo_inc"
    file_contents = {
        "src/a.py": FILE_A,
        "src/b.py": FILE_B,
    }
    file_shas = {
        "src/a.py": "sha_a_v1",
        "src/b.py": "sha_b_v1",
    }

    # 1. Initial indexing: all files must be indexed
    res1 = context_retriever.index_repository_files(repo_id, file_contents, file_shas)
    assert set(res1["reindexed_files"]) == {"src/a.py", "src/b.py"}
    assert res1["skipped_files"] == []
    assert res1["total_symbols_indexed"] == 2

    # 2. Second pass with unchanged SHAs: all files must be skipped
    res2 = context_retriever.index_repository_files(repo_id, file_contents, file_shas)
    assert res2["reindexed_files"] == []
    assert set(res2["skipped_files"]) == {"src/a.py", "src/b.py"}
    assert res2["total_symbols_indexed"] == 0

    # 3. Third pass: modify src/a.py SHA only
    file_contents["src/a.py"] = FILE_A_MODIFIED
    file_shas["src/a.py"] = "sha_a_v2"

    res3 = context_retriever.index_repository_files(repo_id, file_contents, file_shas)
    assert res3["reindexed_files"] == ["src/a.py"]
    assert res3["skipped_files"] == ["src/b.py"]
    assert res3["total_symbols_indexed"] == 1

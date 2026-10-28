import hashlib
import math
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from qdrant_client import QdrantClient, models
from .ast_analyzer import TreeSitterAnalyzer
from .models import (
    CodeSymbol,
    EnclosingScope,
    FileDiff,
    PRContextBundle,
    UpstreamCallSite,
)


def compute_deterministic_vector(text: str, dim: int = 128) -> List[float]:
    """Generates a deterministic unit-length vector for symbol indexing in Qdrant."""
    vec = [0.0] * dim
    words = text.split()
    if not words:
        words = [text]

    for word in words:
        h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        vec[idx] += 1.0

    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    else:
        vec[0] = 1.0
    return vec


class ContextRetriever:
    def __init__(
        self,
        qdrant_client: Optional[QdrantClient] = None,
        collection_name: str = "code_symbols",
        vector_dim: int = 128,
    ):
        self.client = qdrant_client or QdrantClient(":memory:")
        self.collection_name = collection_name
        self.vector_dim = vector_dim
        self.analyzer = TreeSitterAnalyzer()
        # In-memory index cache: (repo_id, file_path) -> git_blob_sha
        self._indexed_shas: Dict[Tuple[str, str], str] = {}
        self._ensure_collection()

    def _ensure_collection(self):
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_dim,
                    distance=models.Distance.COSINE,
                ),
            )

    def is_file_indexed(self, repo_id: str, file_path: str, blob_sha: str) -> bool:
        """Returns True if the file has already been indexed at this exact blob SHA."""
        cached_sha = self._indexed_shas.get((repo_id, file_path))
        return cached_sha == blob_sha

    def delete_file_symbols(self, repo_id: str, file_path: str):
        """Deletes all indexed symbols for a specific file in a repository."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(key="repo_id", match=models.MatchValue(value=repo_id)),
                        models.FieldCondition(key="file_path", match=models.MatchValue(value=file_path)),
                    ]
                )
            ),
        )
        self._indexed_shas.pop((repo_id, file_path), None)

    def index_file(
        self,
        repo_id: str,
        file_path: str,
        source_code: str,
        blob_sha: str,
    ) -> List[CodeSymbol]:
        """
        Parses source code, extracts symbols via Tree-sitter, and indexes them into Qdrant.
        """
        self.delete_file_symbols(repo_id, file_path)

        symbols = self.analyzer.extract_symbols(
            file_path=file_path,
            source_code=source_code,
            repo_id=repo_id,
            blob_sha=blob_sha,
        )

        if not symbols:
            self._indexed_shas[(repo_id, file_path)] = blob_sha
            return []

        points = []
        for sym in symbols:
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, sym.symbol_id))
            vec_text = f"{sym.name} {sym.signature} {sym.docstring or ''}"
            vec = compute_deterministic_vector(vec_text, self.vector_dim)

            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=vec,
                    payload=sym.model_dump(),
                )
            )

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
        )
        self._indexed_shas[(repo_id, file_path)] = blob_sha
        return symbols

    def index_repository_files(
        self,
        repo_id: str,
        file_contents: Dict[str, str],
        file_shas: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Incremental indexer: skips files whose git blob SHA is unchanged.
        """
        reindexed_files: List[str] = []
        skipped_files: List[str] = []
        total_symbols = 0

        for file_path, source_code in file_contents.items():
            current_sha = file_shas.get(file_path, "sha_unknown")
            if self.is_file_indexed(repo_id, file_path, current_sha):
                skipped_files.append(file_path)
                continue

            symbols = self.index_file(repo_id, file_path, source_code, current_sha)
            reindexed_files.append(file_path)
            total_symbols += len(symbols)

        return {
            "reindexed_files": reindexed_files,
            "skipped_files": skipped_files,
            "total_symbols_indexed": total_symbols,
        }

    def retrieve_downstream_symbols(
        self,
        repo_id: str,
        called_symbol_names: List[str],
        exclude_file: str,
    ) -> List[CodeSymbol]:
        """
        Retrieves definitions of symbols called by modified code from other files in the repo.
        """
        if not called_symbol_names:
            return []

        clean_names = list(set(called_symbol_names))
        # Scroll Qdrant for matching symbol names in this repository
        res = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(key="repo_id", match=models.MatchValue(value=repo_id)),
                    models.FieldCondition(key="name", match=models.MatchAny(any=clean_names)),
                ],
                must_not=[
                    models.FieldCondition(key="file_path", match=models.MatchValue(value=exclude_file)),
                ],
            ),
            limit=20,
        )

        downstream: List[CodeSymbol] = []
        for point in res[0]:
            p = point.payload
            downstream.append(CodeSymbol.model_validate(p))
        return downstream

    def retrieve_upstream_call_sites(
        self,
        repo_id: str,
        function_name: str,
        exclude_file: str,
        limit: int = 5,
    ) -> List[UpstreamCallSite]:
        """
        2-hop upstream traversal: finds up to 5 call sites in other files that invoke function_name.
        """
        short_name = function_name.split(".")[-1]

        res = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=models.Filter(
                must=[
                    models.FieldCondition(key="repo_id", match=models.MatchValue(value=repo_id)),
                    models.FieldCondition(key="called_symbols", match=models.MatchAny(any=[short_name, function_name])),
                ],
                must_not=[
                    models.FieldCondition(key="file_path", match=models.MatchValue(value=exclude_file)),
                ],
            ),
            limit=limit,
        )

        call_sites: List[UpstreamCallSite] = []
        for point in res[0]:
            p = point.payload
            source = p.get("source_code", "")
            lines = source.splitlines()

            # Find matching call line
            call_line_offset = 0
            for idx, line in enumerate(lines):
                if short_name in line:
                    call_line_offset = idx
                    break

            start_line = p.get("start_line", 1)
            exact_call_line = start_line + call_line_offset

            call_sites.append(
                UpstreamCallSite(
                    caller_symbol=p.get("name", "unknown"),
                    caller_kind=p.get("kind", "function"),
                    file_path=p.get("file_path", ""),
                    start_line=start_line,
                    end_line=p.get("end_line", 1),
                    call_line=exact_call_line,
                    source_snippet=source,
                )
            )

        return call_sites

    def build_pr_context_bundle(
        self,
        repo_id: str,
        file_diffs: List[FileDiff],
        file_contents: Dict[str, str],
        max_tokens: int = 16000,
    ) -> PRContextBundle:
        """
        Assembles comprehensive 2-hop cross-file context:
        (a) Modified enclosing scopes (functions/classes)
        (b) Downstream symbol definitions imported/called
        (c) Upstream call sites invoking modified functions across other files
        Ranks by call-graph proximity and caps at max_tokens.
        """
        modified_scopes: List[EnclosingScope] = []
        downstream_map: Dict[str, CodeSymbol] = {}
        upstream_call_sites: List[UpstreamCallSite] = []

        # 1. Extract enclosing scopes for each modified file
        for fdiff in file_diffs:
            path = fdiff.new_path
            if path in file_contents and fdiff.modified_line_ranges:
                scopes = self.analyzer.extract_enclosing_scopes(
                    file_path=path,
                    source_code=file_contents[path],
                    modified_line_ranges=fdiff.modified_line_ranges,
                )
                modified_scopes.extend(scopes)

        # 2. For each modified scope, retrieve downstream symbols and upstream call sites
        for scope in modified_scopes:
            # (a) Downstream: symbols called by this scope
            if scope.called_symbols:
                downstream = self.retrieve_downstream_symbols(
                    repo_id=repo_id,
                    called_symbol_names=scope.called_symbols,
                    exclude_file=scope.file_path,
                )
                for sym in downstream:
                    downstream_map[sym.symbol_id] = sym

            # (b) Upstream: other files that call this modified scope
            short_name = scope.name.split(".")[-1]
            callers = self.retrieve_upstream_call_sites(
                repo_id=repo_id,
                function_name=short_name,
                exclude_file=scope.file_path,
                limit=5,
            )
            for c in callers:
                if not any(existing.caller_symbol == c.caller_symbol and existing.file_path == c.file_path for existing in upstream_call_sites):
                    upstream_call_sites.append(c)

        downstream_symbols = list(downstream_map.values())

        # 3. Format Prompt Context & enforce token budget (~3.5 chars / token)
        sections = []
        token_counter = 0

        # Section A: Modified Scopes (Highest priority)
        sections.append("## MODIFIED ENCLOSING SCOPES (Full AST Nodes)")
        for scope in modified_scopes:
            block = (
                f"\n### File: `{scope.file_path}` | Scope: `{scope.name}` ({scope.kind}, Lines {scope.start_line}-{scope.end_line})\n"
                f"```\n{scope.source_code}\n```\n"
            )
            sections.append(block)

        # Section B: Upstream Call Sites (Critical for cross-file breaking change detection)
        if upstream_call_sites:
            sections.append("\n## UPSTREAM CALL SITES (Callers of Modified Functions in Other Files)")
            for call in upstream_call_sites[:5]:
                block = (
                    f"\n### Caller: `{call.caller_symbol}` in `{call.file_path}` (Calls modified function at Line {call.call_line})\n"
                    f"```\n{call.source_snippet}\n```\n"
                )
                sections.append(block)

        # Section C: Downstream Dependencies
        if downstream_symbols:
            sections.append("\n## DOWNSTREAM DEPENDENCIES (Symbols Called/Imported Across Files)")
            for sym in downstream_symbols:
                block = (
                    f"\n### Symbol: `{sym.name}` in `{sym.file_path}` ({sym.kind}, Lines {sym.start_line}-{sym.end_line})\n"
                    f"Signature: `{sym.signature}`\n"
                    f"```\n{sym.source_code}\n```\n"
                )
                sections.append(block)

        formatted_text = "".join(sections)
        estimated_tokens = int(len(formatted_text) / 3.5)

        # Enforce max_tokens truncation if needed
        if estimated_tokens > max_tokens:
            char_limit = int(max_tokens * 3.5)
            formatted_text = formatted_text[:char_limit] + "\n\n... [TRUNCATED DUE TO TOKEN BUDGET] ..."
            estimated_tokens = max_tokens

        return PRContextBundle(
            repo_id=repo_id,
            modified_scopes=modified_scopes,
            downstream_symbols=downstream_symbols,
            upstream_call_sites=upstream_call_sites,
            estimated_tokens=estimated_tokens,
            formatted_prompt_context=formatted_text,
        )

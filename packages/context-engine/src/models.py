from typing import List, Literal, Optional, Tuple
from pydantic import BaseModel, Field, ConfigDict


class DiffHunk(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    old_start: int = Field(..., description="Starting line in old file")
    old_lines: int = Field(..., description="Line count in old file")
    new_start: int = Field(..., description="Starting line in new file")
    new_lines: int = Field(..., description="Line count in new file")
    header: str = Field(..., description="Hunk header e.g. @@ -10,5 +10,7 @@")
    lines: List[str] = Field(default_factory=list, description="Raw hunk lines")
    modified_lines: List[int] = Field(
        default_factory=list,
        description="1-based line numbers in the new file that were added or modified"
    )


class FileDiff(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    old_path: Optional[str] = None
    new_path: str
    is_new: bool = False
    is_deleted: bool = False
    is_renamed: bool = False
    hunks: List[DiffHunk] = Field(default_factory=list)
    modified_line_ranges: List[Tuple[int, int]] = Field(
        default_factory=list,
        description="Consolidated 1-based [start_line, end_line] inclusive modified intervals"
    )


class EnclosingScope(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    kind: Literal["function", "method", "class", "interface", "module"]
    file_path: str
    start_line: int
    end_line: int
    docstring: Optional[str] = None
    source_code: str
    called_symbols: List[str] = Field(default_factory=list)
    imported_symbols: List[str] = Field(default_factory=list)
    type_references: List[str] = Field(default_factory=list)


class CodeSymbol(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    symbol_id: str
    repo_id: str
    name: str
    kind: Literal["function", "method", "class", "interface"]
    file_path: str
    start_line: int
    end_line: int
    signature: str
    docstring: Optional[str] = None
    source_code: str
    called_symbols: List[str] = Field(default_factory=list)
    imported_symbols: List[str] = Field(default_factory=list)
    type_references: List[str] = Field(default_factory=list)
    blob_sha: str
    node_hash: str


class UpstreamCallSite(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    caller_symbol: str
    caller_kind: str
    file_path: str
    start_line: int
    end_line: int
    call_line: int
    source_snippet: str


class PRContextBundle(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    repo_id: str
    modified_scopes: List[EnclosingScope] = Field(default_factory=list)
    downstream_symbols: List[CodeSymbol] = Field(default_factory=list)
    upstream_call_sites: List[UpstreamCallSite] = Field(default_factory=list)
    estimated_tokens: int = 0
    formatted_prompt_context: str = ""

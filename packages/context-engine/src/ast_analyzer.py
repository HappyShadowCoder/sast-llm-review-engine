import ast
import hashlib
from pathlib import Path
import re
from typing import Dict, List, Optional, Set, Tuple

from tree_sitter import Language, Node, Parser
import tree_sitter_python as tspython
import tree_sitter_typescript as tstypescript
import tree_sitter_go as tsgo

from .models import CodeSymbol, EnclosingScope


class TreeSitterAnalyzer:
    def __init__(self):
        self._languages: Dict[str, Language] = {}
        self._init_parsers()

    def _init_parsers(self):
        try:
            self._languages["python"] = Language(tspython.language())
            self._languages["typescript"] = Language(tstypescript.language_typescript())
            self._languages["tsx"] = Language(tstypescript.language_tsx())
            self._languages["go"] = Language(tsgo.language())
        except Exception:
            pass

    def detect_language(self, file_path: str) -> Optional[str]:
        clean_path = str(file_path).replace("\\", "/")
        dot_idx = clean_path.rfind(".")
        ext = clean_path[dot_idx:].lower() if dot_idx != -1 else ""
        if ext == ".py":
            return "python"
        elif ext in {".ts", ".js", ".mjs", ".cjs"}:
            return "typescript"
        elif ext in {".tsx", ".jsx"}:
            return "tsx"
        elif ext == ".go":
            return "go"
        return None

    def get_parser(self, language: str) -> Optional[Parser]:
        lang_obj = self._languages.get(language)
        if lang_obj:
            try:
                return Parser(lang_obj)
            except Exception:
                return None
        return None

    def parse_source(self, file_path: str, source_code: str):
        lang = self.detect_language(file_path)
        if not lang:
            return None, None
        parser = self.get_parser(lang)
        if not parser:
            return None, None
        try:
            source_bytes = source_code.encode("utf-8")
            tree = parser.parse(source_bytes)
            return tree, source_bytes
        except Exception:
            return None, None

    def extract_symbols(
        self,
        file_path: str,
        source_code: str,
        repo_id: str = "default",
        blob_sha: str = "head",
    ) -> List[CodeSymbol]:
        """
        Extracts all top-level and member functions, classes, and methods as CodeSymbols.
        Uses native Python AST for Python (100% segfault-proof & instant) and Tree-sitter for TS/JS/Go.
        """
        lang = self.detect_language(file_path)
        if lang == "python":
            return self._extract_python_symbols_native(file_path, source_code, repo_id, blob_sha)
        
        # Non-python: use Tree-sitter with error boundary and regex fallback
        try:
            return self._extract_symbols_treesitter(file_path, source_code, repo_id, blob_sha)
        except Exception:
            return self._extract_symbols_regex(file_path, source_code, repo_id, blob_sha)

    def _extract_python_symbols_native(
        self,
        file_path: str,
        source_code: str,
        repo_id: str,
        blob_sha: str,
    ) -> List[CodeSymbol]:
        """
        100% CPython segfault-safe AST extractor for Python source files.
        """
        symbols: List[CodeSymbol] = []
        source_lines = source_code.splitlines()

        # Extract imports
        imports = []
        for line in source_lines:
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                imports.append(stripped)

        try:
            parsed = ast.parse(source_code)
        except Exception:
            return self._extract_symbols_regex(file_path, source_code, repo_id, blob_sha)

        def walk_node(node: ast.AST, class_prefix: str = ""):
            for child in getattr(node, "body", []):
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = child.name
                    full_name = f"{class_prefix}.{name}" if class_prefix else name
                    kind = "method" if class_prefix else "function"
                    start_line = child.lineno
                    end_line = getattr(child, "end_lineno", child.lineno)

                    s_idx = max(0, start_line - 1)
                    e_idx = min(len(source_lines), end_line)
                    snippet = "\n".join(source_lines[s_idx:e_idx])
                    sig_line = source_lines[s_idx].strip() if s_idx < len(source_lines) else f"def {name}()"
                    docstring = ast.get_docstring(child)

                    # Extract outgoing calls
                    calls = set()
                    for sub in ast.walk(child):
                        if isinstance(sub, ast.Call):
                            if isinstance(sub.func, ast.Name):
                                calls.add(sub.func.id)
                            elif isinstance(sub.func, ast.Attribute):
                                calls.add(sub.func.attr)

                    symbols.append(
                        CodeSymbol(
                            symbol_id=f"{repo_id}:{file_path}:{full_name}:{start_line}",
                            repo_id=repo_id,
                            name=full_name,
                            kind=kind,
                            file_path=file_path,
                            start_line=start_line,
                            end_line=end_line,
                            signature=sig_line.rstrip(":{ "),
                            docstring=docstring,
                            source_code=snippet,
                            called_symbols=list(calls),
                            imported_symbols=imports,
                            type_references=[],
                            blob_sha=blob_sha,
                            node_hash=hashlib.sha256(snippet.encode("utf-8")).hexdigest(),
                        )
                    )
                    # Walk nested functions/classes
                    walk_node(child, class_prefix=full_name)

                elif isinstance(child, ast.ClassDef):
                    name = child.name
                    full_name = f"{class_prefix}.{name}" if class_prefix else name
                    start_line = child.lineno
                    end_line = getattr(child, "end_lineno", child.lineno)

                    s_idx = max(0, start_line - 1)
                    e_idx = min(len(source_lines), end_line)
                    snippet = "\n".join(source_lines[s_idx:e_idx])
                    sig_line = source_lines[s_idx].strip() if s_idx < len(source_lines) else f"class {name}:"
                    docstring = ast.get_docstring(child)

                    symbols.append(
                        CodeSymbol(
                            symbol_id=f"{repo_id}:{file_path}:{full_name}:{start_line}",
                            repo_id=repo_id,
                            name=full_name,
                            kind="class",
                            file_path=file_path,
                            start_line=start_line,
                            end_line=end_line,
                            signature=sig_line.rstrip(":{ "),
                            docstring=docstring,
                            source_code=snippet,
                            called_symbols=[],
                            imported_symbols=imports,
                            type_references=[],
                            blob_sha=blob_sha,
                            node_hash=hashlib.sha256(snippet.encode("utf-8")).hexdigest(),
                        )
                    )
                    walk_node(child, class_prefix=full_name)

        walk_node(parsed)
        return symbols

    def _extract_symbols_treesitter(
        self,
        file_path: str,
        source_code: str,
        repo_id: str,
        blob_sha: str,
    ) -> List[CodeSymbol]:
        tree, source_bytes = self.parse_source(file_path, source_code)
        if not tree or not source_bytes:
            return self._extract_symbols_regex(file_path, source_code, repo_id, blob_sha)

        lang = self.detect_language(file_path)
        file_imports = self._extract_file_imports(tree.root_node, source_bytes, lang)
        symbols: List[CodeSymbol] = []

        CONTAINER_TYPES = {
            "module", "source_file", "class_definition", "class_declaration",
            "class_body", "function_definition", "function_declaration",
            "method_definition", "method_declaration", "decorated_definition",
            "export_statement", "type_declaration", "interface_declaration",
        }

        def visitor(node: Node, class_prefix: str = "", is_in_class: bool = False):
            try:
                actual_node = node
                outer_sym_node = node
                if node.type == "decorated_definition":
                    for child in node.named_children:
                        if child.type in {"function_definition", "class_definition"}:
                            actual_node = child
                            break
                elif node.type == "export_statement":
                    for child in node.named_children:
                        if child.type in {"function_declaration", "class_declaration", "interface_declaration", "type_alias_declaration"}:
                            actual_node = child
                            break

                kind = self._get_node_kind(actual_node, lang, is_in_class=is_in_class)
                if kind:
                    name = self._get_node_name(actual_node, source_bytes, lang)
                    if name:
                        full_name = f"{class_prefix}.{name}" if class_prefix else name
                        sb_len = len(source_bytes)
                        s_byte = max(0, min(sb_len, outer_sym_node.start_byte))
                        e_byte = max(s_byte, min(sb_len, outer_sym_node.end_byte))
                        start_line = max(1, outer_sym_node.start_point.row + 1)
                        end_line = max(start_line, outer_sym_node.end_point.row + 1)
                        source_snippet = source_bytes[s_byte:e_byte].decode("utf-8", errors="replace")
                        signature = self._extract_signature(actual_node, source_bytes, lang)
                        docstring = self._extract_docstring(actual_node, source_bytes, lang)
                        calls = self._extract_calls(actual_node, source_bytes, lang)
                        types = self._extract_type_references(actual_node, source_bytes, lang)
                        node_hash = hashlib.sha256(source_snippet.encode("utf-8")).hexdigest()
                        symbol_id = f"{repo_id}:{file_path}:{full_name}:{start_line}"

                        symbols.append(
                            CodeSymbol(
                                symbol_id=symbol_id,
                                repo_id=repo_id,
                                name=full_name,
                                kind=kind,
                                file_path=file_path,
                                start_line=start_line,
                                end_line=end_line,
                                signature=signature,
                                docstring=docstring,
                                source_code=source_snippet,
                                called_symbols=list(calls),
                                imported_symbols=file_imports,
                                type_references=list(types),
                                blob_sha=blob_sha,
                                node_hash=node_hash,
                            )
                        )
                        child_is_class = kind in {"class", "interface"}
                        for child in actual_node.named_children:
                            if child.type in CONTAINER_TYPES:
                                visitor(child, class_prefix=full_name, is_in_class=child_is_class)
                        return

                child_is_class = is_in_class or (node.type in {"class_definition", "class_declaration", "class_body"})
                for child in node.named_children:
                    if child.type in CONTAINER_TYPES:
                        visitor(child, class_prefix=class_prefix, is_in_class=child_is_class)
            except Exception:
                pass

        visitor(tree.root_node)
        return symbols

    def _extract_symbols_regex(
        self,
        file_path: str,
        source_code: str,
        repo_id: str,
        blob_sha: str,
    ) -> List[CodeSymbol]:
        """Regex-based fast fallback for any syntax errors or unsupported languages."""
        symbols = []
        lines = source_code.splitlines()
        pattern = re.compile(r"^\s*(?:export\s+)?(?:async\s+)?(function|class|def|type|interface)\s+([a-zA-Z0-9_]+)", re.MULTILINE)

        for match in pattern.finditer(source_code):
            kind_str = match.group(1)
            name = match.group(2)
            kind = "class" if kind_str in {"class", "type", "interface"} else "function"
            line_no = source_code[:match.start()].count("\n") + 1
            end_line = min(len(lines), line_no + 20)
            snippet = "\n".join(lines[line_no - 1 : end_line])

            symbols.append(
                CodeSymbol(
                    symbol_id=f"{repo_id}:{file_path}:{name}:{line_no}",
                    repo_id=repo_id,
                    name=name,
                    kind=kind,
                    file_path=file_path,
                    start_line=line_no,
                    end_line=end_line,
                    signature=lines[line_no - 1].strip() if line_no <= len(lines) else "",
                    docstring=None,
                    source_code=snippet,
                    called_symbols=[],
                    imported_symbols=[],
                    type_references=[],
                    blob_sha=blob_sha,
                    node_hash=hashlib.sha256(snippet.encode("utf-8")).hexdigest(),
                )
            )
        return symbols

    def extract_enclosing_scopes(
        self,
        file_path: str,
        source_code: str,
        modified_line_ranges: List[Tuple[int, int]],
    ) -> List[EnclosingScope]:
        """
        Given a source file and modified line ranges, extracts the full enclosing function,
        method, or class AST node along with start/end lines and dependencies.
        """
        symbols = self.extract_symbols(file_path, source_code)
        matched_scopes: List[EnclosingScope] = []
        covered_ranges = set()

        for range_idx, (r_start, r_end) in enumerate(modified_line_ranges):
            matching = []
            for s in symbols:
                if s.start_line <= r_end and s.end_line >= r_start:
                    span = s.end_line - s.start_line
                    matching.append((span, s))

            if matching:
                matching.sort(key=lambda x: x[0])
                _, best = matching[0]
                scope = EnclosingScope(
                    name=best.name,
                    kind=best.kind,
                    file_path=file_path,
                    start_line=best.start_line,
                    end_line=best.end_line,
                    docstring=best.docstring,
                    source_code=best.source_code,
                    called_symbols=best.called_symbols,
                    imported_symbols=best.imported_symbols,
                    type_references=best.type_references,
                )
                if scope not in matched_scopes:
                    matched_scopes.append(scope)
                covered_ranges.add(range_idx)

        # Fallback for modified ranges outside functions (top-level code)
        lines = source_code.splitlines()
        for range_idx, (r_start, r_end) in enumerate(modified_line_ranges):
            if range_idx not in covered_ranges:
                s_idx = max(0, r_start - 1)
                e_idx = min(len(lines), r_end)
                snippet = "\n".join(lines[s_idx:e_idx])
                mod_name = str(file_path).replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0] or "module"
                scope = EnclosingScope(
                    name=mod_name,
                    kind="module",
                    file_path=file_path,
                    start_line=r_start,
                    end_line=r_end,
                    docstring=None,
                    source_code=snippet,
                    called_symbols=[],
                    imported_symbols=[],
                    type_references=[],
                )
                matched_scopes.append(scope)

        return matched_scopes

    def _get_node_kind(self, node: Node, lang: str, is_in_class: bool = False) -> Optional[str]:
        ntype = node.type
        if lang == "python":
            if ntype == "function_definition":
                return "method" if is_in_class else "function"
            elif ntype == "class_definition":
                return "class"
        elif lang in {"typescript", "tsx"}:
            if ntype in {"function_declaration", "function_expression", "arrow_function"}:
                return "function"
            elif ntype == "method_definition":
                return "method"
            elif ntype in {"class_declaration", "class"}:
                return "class"
            elif ntype == "interface_declaration":
                return "interface"
        elif lang == "go":
            if ntype == "function_declaration":
                return "function"
            elif ntype == "method_declaration":
                return "method"
            elif ntype == "type_declaration":
                return "class"
        return None

    def _safe_slice(self, source_bytes: bytes, start_byte: int, end_byte: int) -> str:
        try:
            sb_len = len(source_bytes)
            s = int(max(0, min(sb_len, start_byte)))
            e = int(max(s, min(sb_len, end_byte)))
            return source_bytes[s:e].decode("utf-8", errors="replace")
        except Exception:
            return ""

    def _get_node_name(self, node: Node, source_bytes: bytes, lang: str) -> Optional[str]:
        try:
            name_node = node.child_by_field_name("name")
            if name_node:
                return self._safe_slice(source_bytes, name_node.start_byte, name_node.end_byte)
        except Exception:
            pass
        return None

    def _extract_signature(self, node: Node, source_bytes: bytes, lang: str) -> str:
        try:
            snippet = self._safe_slice(source_bytes, node.start_byte, node.end_byte)
            if not snippet:
                return ""
            return snippet.splitlines()[0].strip().rstrip(":{ \n\r")
        except Exception:
            return ""

    def _extract_docstring(self, node: Node, source_bytes: bytes, lang: str) -> Optional[str]:
        try:
            body = node.child_by_field_name("body")
            if not body:
                return None
            for child in body.named_children:
                if child.type == "expression_statement":
                    for sub in child.named_children:
                        if sub.type == "string":
                            raw = self._safe_slice(source_bytes, sub.start_byte, sub.end_byte)
                            return raw.strip("\"' \n\t")
        except Exception:
            pass
        return None

    def _extract_calls(self, node: Node, source_bytes: bytes, lang: str) -> Set[str]:
        calls = set()
        try:
            stack = [node]
            sb_len = len(source_bytes)
            while stack:
                curr = stack.pop()
                if curr.type in {"call", "call_expression"}:
                    func_node = curr.child_by_field_name("function")
                    if func_node:
                        s_b = max(0, min(sb_len, func_node.start_byte))
                        e_b = max(s_b, min(sb_len, func_node.end_byte))
                        raw_call = source_bytes[s_b:e_b].decode("utf-8", errors="replace")
                        parts = raw_call.split(".")
                        symbol_call = parts[-1].strip()
                        if symbol_call.isidentifier():
                            calls.add(symbol_call)
                        if len(parts) > 1:
                            calls.add(raw_call.strip())
                for child in reversed(curr.named_children):
                    stack.append(child)
        except Exception:
            pass
        return calls

    def _extract_type_references(self, node: Node, source_bytes: bytes, lang: str) -> Set[str]:
        types = set()
        try:
            stack = [node]
            sb_len = len(source_bytes)
            while stack:
                curr = stack.pop()
                if curr.type in {"type_identifier", "type", "type_reference"}:
                    s_b = max(0, min(sb_len, curr.start_byte))
                    e_b = max(s_b, min(sb_len, curr.end_byte))
                    raw = source_bytes[s_b:e_b].decode("utf-8", errors="replace").strip()
                    if raw and raw.isidentifier():
                        types.add(raw)
                for child in reversed(curr.named_children):
                    stack.append(child)
        except Exception:
            pass
        return types

    def _extract_file_imports(self, root_node: Node, source_bytes: bytes, lang: str) -> List[str]:
        imports = []
        try:
            stack = [root_node]
            sb_len = len(source_bytes)
            while stack:
                curr = stack.pop()
                s_b = max(0, min(sb_len, curr.start_byte))
                e_b = max(s_b, min(sb_len, curr.end_byte))
                if lang == "python" and curr.type in {"import_statement", "import_from_statement"}:
                    imports.append(source_bytes[s_b:e_b].decode("utf-8", errors="replace").strip())
                elif lang in {"typescript", "tsx"} and curr.type == "import_statement":
                    imports.append(source_bytes[s_b:e_b].decode("utf-8", errors="replace").strip())
                elif lang == "go" and curr.type in {"import_declaration", "import_spec"}:
                    imports.append(source_bytes[s_b:e_b].decode("utf-8", errors="replace").strip())
                for child in reversed(curr.named_children):
                    stack.append(child)
        except Exception:
            pass
        return imports

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from tree_sitter import Language, Node, Parser
import tree_sitter_python as tspython
import tree_sitter_typescript as tstypescript
import tree_sitter_go as tsgo

from .models import CodeSymbol, EnclosingScope


class TreeSitterAnalyzer:
    def __init__(self):
        self._parsers: Dict[str, Parser] = {}
        self._init_parsers()

    def _init_parsers(self):
        py_lang = Language(tspython.language())
        ts_lang = Language(tstypescript.language_typescript())
        tsx_lang = Language(tstypescript.language_tsx())
        go_lang = Language(tsgo.language())

        self._parsers["python"] = Parser(py_lang)
        self._parsers["typescript"] = Parser(ts_lang)
        self._parsers["tsx"] = Parser(tsx_lang)
        self._parsers["go"] = Parser(go_lang)

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
        return self._parsers.get(language)

    def parse_source(self, file_path: str, source_code: str):
        lang = self.detect_language(file_path)
        if not lang:
            return None, None
        parser = self.get_parser(lang)
        if not parser:
            return None, None
        source_bytes = source_code.encode("utf-8")
        tree = parser.parse(source_bytes)
        return tree, source_bytes

    def extract_symbols(
        self,
        file_path: str,
        source_code: str,
        repo_id: str = "default",
        blob_sha: str = "head",
    ) -> List[CodeSymbol]:
        """
        Extracts all top-level and member functions, classes, and methods as CodeSymbols.
        """
        tree, source_bytes = self.parse_source(file_path, source_code)
        if not tree or not source_bytes:
            return []

        lang = self.detect_language(file_path)
        file_imports = self._extract_file_imports(tree.root_node, source_bytes, lang)
        symbols: List[CodeSymbol] = []

        CONTAINER_TYPES = {
            "module",
            "source_file",
            "class_definition",
            "class_declaration",
            "class_body",
            "function_definition",
            "function_declaration",
            "method_definition",
            "method_declaration",
            "decorated_definition",
            "export_statement",
            "statement_block",
            "block",
            "type_declaration",
            "interface_declaration",
        }

        def visitor(node: Node, class_prefix: str = ""):
            # Handle Python decorated functions / classes
            actual_node = node
            if node.type == "decorated_definition":
                for child in node.named_children:
                    if child.type in {"function_definition", "class_definition"}:
                        actual_node = child
                        break

            # Handle TypeScript export statement wrapper
            elif node.type == "export_statement":
                for child in node.named_children:
                    if child.type in {"function_declaration", "class_declaration", "interface_declaration", "type_alias_declaration"}:
                        actual_node = child
                        break

            kind = self._get_node_kind(actual_node, lang)
            if kind:
                name = self._get_node_name(actual_node, source_bytes, lang)
                if name:
                    full_name = f"{class_prefix}.{name}" if class_prefix else name
                    outer_sym_node = actual_node
                    if actual_node.parent and actual_node.parent.type in {"export_statement", "decorated_definition"}:
                        outer_sym_node = actual_node.parent

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

                    symbol = CodeSymbol(
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
                    symbols.append(symbol)

                    # Recurse only into container children of class or function
                    for child in actual_node.named_children:
                        if child.type in CONTAINER_TYPES:
                            visitor(child, class_prefix=full_name)
                    return

            for child in node.named_children:
                if child.type in CONTAINER_TYPES:
                    visitor(child, class_prefix=class_prefix)

        visitor(tree.root_node)
        return symbols

    def extract_enclosing_scopes(
        self,
        file_path: str,
        source_code: str,
        modified_line_ranges: List[Tuple[int, int]],
    ) -> List[EnclosingScope]:
        """
        Given a source file and modified line ranges, extracts the full enclosing function,
        method, or class AST node (never truncated mid-function) along with its start/end lines,
        docstring, and outgoing calls/imports.
        """
        tree, source_bytes = self.parse_source(file_path, source_code)
        if not tree or not source_bytes:
            return []

        lang = self.detect_language(file_path)
        file_imports = self._extract_file_imports(tree.root_node, source_bytes, lang)
        candidates: List[Tuple[Node, str, str]] = []  # (node, kind, name)

        CONTAINER_TYPES = {
            "module",
            "source_file",
            "class_definition",
            "class_declaration",
            "class_body",
            "function_definition",
            "function_declaration",
            "method_definition",
            "method_declaration",
            "decorated_definition",
            "export_statement",
            "statement_block",
            "block",
            "type_declaration",
            "interface_declaration",
        }

        def collect_candidates(node: Node, class_prefix: str = ""):
            actual = node
            if node.type == "decorated_definition":
                for child in node.named_children:
                    if child.type in {"function_definition", "class_definition"}:
                        actual = child
                        break
            elif node.type == "export_statement":
                for child in node.named_children:
                    if child.type in {"function_declaration", "class_declaration", "interface_declaration"}:
                        actual = child
                        break

            kind = self._get_node_kind(actual, lang)
            name = self._get_node_name(actual, source_bytes, lang)
            if kind and name:
                full_name = f"{class_prefix}.{name}" if class_prefix else name
                candidates.append((actual, kind, full_name))
                for child in actual.named_children:
                    if child.type in CONTAINER_TYPES:
                        collect_candidates(child, class_prefix=full_name)
                return

            for child in node.named_children:
                if child.type in CONTAINER_TYPES:
                    collect_candidates(child, class_prefix=class_prefix)

        collect_candidates(tree.root_node)

        matched_scopes: List[EnclosingScope] = []
        covered_ranges = set()

        # For each modified range, find the tightest enclosing scope
        for range_idx, (r_start, r_end) in enumerate(modified_line_ranges):
            matching_nodes = []
            for node, kind, name in candidates:
                n_start = max(1, node.start_point.row + 1)
                n_end = max(n_start, node.end_point.row + 1)
                # Check overlap
                if n_start <= r_end and n_end >= r_start:
                    span = n_end - n_start
                    matching_nodes.append((span, node, kind, name))

            if matching_nodes:
                # Pick innermost scope (smallest span)
                matching_nodes.sort(key=lambda x: x[0])
                _, best_node, kind, name = matching_nodes[0]

                # If wrapped in export or decorator, include it in start_line and source_code
                outer_node = best_node
                if best_node.parent and best_node.parent.type in {"export_statement", "decorated_definition"}:
                    outer_node = best_node.parent

                sb_len = len(source_bytes)
                s_byte = max(0, min(sb_len, outer_node.start_byte))
                e_byte = max(s_byte, min(sb_len, outer_node.end_byte))
                n_start = max(1, outer_node.start_point.row + 1)
                n_end = max(n_start, outer_node.end_point.row + 1)
                source_snippet = source_bytes[s_byte:e_byte].decode("utf-8", errors="replace")
                docstring = self._extract_docstring(best_node, source_bytes, lang)
                calls = self._extract_calls(best_node, source_bytes, lang)
                types = self._extract_type_references(best_node, source_bytes, lang)

                scope = EnclosingScope(
                    name=name,
                    kind=kind,
                    file_path=file_path,
                    start_line=n_start,
                    end_line=n_end,
                    docstring=docstring,
                    source_code=source_snippet,
                    called_symbols=list(calls),
                    imported_symbols=file_imports,
                    type_references=list(types),
                )
                if scope not in matched_scopes:
                    matched_scopes.append(scope)
                covered_ranges.add(range_idx)

        # For any modified ranges outside of functions/classes (e.g. top-level imports or configs),
        # create a module-level enclosing scope
        for range_idx, (r_start, r_end) in enumerate(modified_line_ranges):
            if range_idx not in covered_ranges:
                lines = source_code.splitlines()
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
                    imported_symbols=file_imports,
                    type_references=[],
                )
                matched_scopes.append(scope)

        return matched_scopes

    def _get_node_kind(self, node: Node, lang: str) -> Optional[str]:
        ntype = node.type
        if lang == "python":
            if ntype == "function_definition":
                # Check if inside class
                parent = node.parent
                while parent:
                    if parent.type == "class_definition":
                        return "method"
                    parent = parent.parent
                return "function"
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
        sb_len = len(source_bytes)
        s = max(0, min(sb_len, start_byte))
        e = max(s, min(sb_len, end_byte))
        return source_bytes[s:e].decode("utf-8", errors="replace")

    def _get_node_name(self, node: Node, source_bytes: bytes, lang: str) -> Optional[str]:
        name_node = node.child_by_field_name("name")
        if name_node:
            return self._safe_slice(source_bytes, name_node.start_byte, name_node.end_byte)

        # Fallbacks for arrow functions assigned to variables: const foo = () => ...
        if node.type == "arrow_function" and node.parent and node.parent.type == "variable_declarator":
            v_name = node.parent.child_by_field_name("name")
            if v_name:
                return self._safe_slice(source_bytes, v_name.start_byte, v_name.end_byte)

        # Go type declarations: type MyStruct struct { ... }
        if node.type == "type_declaration":
            for child in node.named_children:
                if child.type == "type_spec":
                    n = child.child_by_field_name("name")
                    if n:
                        return self._safe_slice(source_bytes, n.start_byte, n.end_byte)

        return None

    def _extract_signature(self, node: Node, source_bytes: bytes, lang: str) -> str:
        # Extract first line or header up to the body
        body_node = node.child_by_field_name("body")
        if body_node:
            sig = self._safe_slice(source_bytes, node.start_byte, body_node.start_byte).strip()
            return sig.rstrip(":{ \n\r")
        # Fallback to first line
        snippet = self._safe_slice(source_bytes, node.start_byte, node.end_byte)
        return snippet.splitlines()[0].strip() if snippet else ""

    def _extract_docstring(self, node: Node, source_bytes: bytes, lang: str) -> Optional[str]:
        body = node.child_by_field_name("body")
        if not body:
            return None

        if lang == "python":
            for child in body.named_children:
                if child.type == "expression_statement":
                    for sub in child.named_children:
                        if sub.type == "string":
                            raw = self._safe_slice(source_bytes, sub.start_byte, sub.end_byte)
                            return raw.strip("\"' \n\t")
        elif lang in {"typescript", "tsx", "go"}:
            # Check comment immediately preceding node
            prev = node.prev_sibling
            if prev and prev.type in {"comment", "block_comment", "line_comment"}:
                return self._safe_slice(source_bytes, prev.start_byte, prev.end_byte).strip("/ \n\t*")

        return None

    def _extract_calls(self, node: Node, source_bytes: bytes, lang: str) -> Set[str]:
        calls = set()
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

        return calls

    def _extract_type_references(self, node: Node, source_bytes: bytes, lang: str) -> Set[str]:
        types = set()
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

        return types

    def _extract_file_imports(self, root_node: Node, source_bytes: bytes, lang: str) -> List[str]:
        imports = []
        stack = [root_node]
        sb_len = len(source_bytes)

        while stack:
            curr = stack.pop()
            s_b = max(0, min(sb_len, curr.start_byte))
            e_b = max(s_b, min(sb_len, curr.end_byte))

            if lang == "python":
                if curr.type in {"import_statement", "import_from_statement"}:
                    raw = source_bytes[s_b:e_b].decode("utf-8", errors="replace").strip()
                    imports.append(raw)
            elif lang in {"typescript", "tsx"}:
                if curr.type == "import_statement":
                    raw = source_bytes[s_b:e_b].decode("utf-8", errors="replace").strip()
                    imports.append(raw)
            elif lang == "go":
                if curr.type in {"import_declaration", "import_spec"}:
                    raw = source_bytes[s_b:e_b].decode("utf-8", errors="replace").strip()
                    imports.append(raw)

            for child in reversed(curr.named_children):
                stack.append(child)

        return imports

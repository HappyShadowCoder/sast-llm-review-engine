import re
from typing import List, Optional, Tuple
from .models import DiffHunk, FileDiff

HUNK_HEADER_REGEX = re.compile(
    r"^@@\s+-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@(.*)$"
)


class UnifiedDiffParser:
    @classmethod
    def parse(cls, diff_text: str) -> List[FileDiff]:
        """
        Parses a unified git diff string into a list of structured FileDiff objects.
        """
        if not diff_text or not diff_text.strip():
            return []

        file_diffs: List[FileDiff] = []
        raw_lines = diff_text.splitlines()

        current_file: Optional[FileDiff] = None
        current_hunk: Optional[DiffHunk] = None
        new_line_cursor = 0

        i = 0
        n = len(raw_lines)

        while i < n:
            line = raw_lines[i]

            # Detect file boundaries
            if line.startswith("diff --git "):
                if current_file:
                    if current_hunk:
                        current_file.hunks.append(current_hunk)
                        current_hunk = None
                    current_file.modified_line_ranges = cls._merge_line_ranges(current_file.hunks)
                    file_diffs.append(current_file)

                # Parse paths: diff --git a/path/to/file b/path/to/file
                parts = line.split(" ")
                old_path = parts[2][2:] if len(parts) > 2 and parts[2].startswith("a/") else (parts[2] if len(parts) > 2 else "")
                new_path = parts[3][2:] if len(parts) > 3 and parts[3].startswith("b/") else (parts[3] if len(parts) > 3 else old_path)

                current_file = FileDiff(
                    old_path=old_path,
                    new_path=new_path,
                )
                current_hunk = None
                i += 1
                continue

            if current_file:
                if line.startswith("new file mode"):
                    current_file.is_new = True
                elif line.startswith("deleted file mode"):
                    current_file.is_deleted = True
                elif line.startswith("rename from"):
                    current_file.is_renamed = True
                elif line.startswith("--- "):
                    p = line[4:].strip()
                    if p == "/dev/null":
                        current_file.old_path = None
                    elif p.startswith("a/"):
                        current_file.old_path = p[2:]
                    else:
                        current_file.old_path = p
                elif line.startswith("+++ "):
                    p = line[4:].strip()
                    if p == "/dev/null":
                        current_file.new_path = ""
                        current_file.is_deleted = True
                    elif p.startswith("b/"):
                        current_file.new_path = p[2:]
                    else:
                        current_file.new_path = p

            # Check for Hunk header: @@ -old_start,old_lines +new_start,new_lines @@
            match = HUNK_HEADER_REGEX.match(line)
            if match:
                if current_file:
                    if current_hunk:
                        current_file.hunks.append(current_hunk)

                old_start = int(match.group(1))
                old_lines = int(match.group(2)) if match.group(2) is not None else 1
                new_start = int(match.group(3))
                new_lines = int(match.group(4)) if match.group(4) is not None else 1
                header = line

                current_hunk = DiffHunk(
                    old_start=old_start,
                    old_lines=old_lines,
                    new_start=new_start,
                    new_lines=new_lines,
                    header=header,
                    lines=[],
                    modified_lines=[],
                )
                new_line_cursor = new_start

                if not current_file:
                    # In case diff started directly with @@ without diff --git header
                    current_file = FileDiff(
                        old_path="unknown",
                        new_path="unknown",
                    )
                i += 1
                continue

            if current_hunk:
                current_hunk.lines.append(line)
                if line.startswith("+") and not line.startswith("+++"):
                    current_hunk.modified_lines.append(new_line_cursor)
                    new_line_cursor += 1
                elif line.startswith("-") and not line.startswith("---"):
                    # Deletion: associate with current line in new file
                    mod_line = max(1, new_line_cursor)
                    if mod_line not in current_hunk.modified_lines:
                        current_hunk.modified_lines.append(mod_line)
                elif line.startswith(" ") or line == "":
                    # Context line
                    new_line_cursor += 1
                elif line.startswith("\\ No newline at end of file"):
                    pass

            i += 1

        if current_file:
            if current_hunk:
                current_file.hunks.append(current_hunk)
            current_file.modified_line_ranges = cls._merge_line_ranges(current_file.hunks)
            file_diffs.append(current_file)

        return file_diffs

    @staticmethod
    def _merge_line_ranges(hunks: List[DiffHunk]) -> List[Tuple[int, int]]:
        """
        Consolidates all modified lines across hunks into sorted, non-overlapping [start, end] ranges.
        """
        all_lines = set()
        for hunk in hunks:
            all_lines.update(hunk.modified_lines)

        if not all_lines:
            return []

        sorted_lines = sorted(all_lines)
        ranges: List[Tuple[int, int]] = []
        range_start = sorted_lines[0]
        range_end = sorted_lines[0]

        for line in sorted_lines[1:]:
            if line == range_end + 1:
                range_end = line
            else:
                ranges.append((range_start, range_end))
                range_start = line
                range_end = line

        ranges.append((range_start, range_end))
        return ranges

import os
import fnmatch
import argparse
from pathlib import Path


# ---------------------------------------------------------------------
# 🧠 Helpers
# ---------------------------------------------------------------------
def load_gitignore_patterns(gitignore_path: Path) -> list[str]:
    """Load patterns from .gitignore if available."""
    patterns = []
    if gitignore_path.exists():
        with open(gitignore_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                patterns.append(line)
    return patterns


def is_ignored(path: Path, patterns: list[str], base_dir: Path) -> bool:
    """Check if file path matches any .gitignore pattern."""
    rel_path = path.relative_to(base_dir).as_posix()
    for pat in patterns:
        if fnmatch.fnmatch(rel_path, pat) or fnmatch.fnmatch(rel_path, f"*/{pat}"):
            return True
    return False


def collect_python_files(base_dir: Path, patterns: list[str], exclude_self: Path, max_size: int | None) -> list[Path]:
    """Collect .py files while skipping ignored/system paths, self, and large files."""
    files = []
    for path in base_dir.rglob("*.py"):
        # Skip unwanted folders
        if any(part in {".venv", "__pycache__", ".git", "node_modules"} for part in path.parts):
            continue
        # Skip ignored patterns
        if is_ignored(path, patterns, base_dir):
            continue
        # Skip self
        if path.resolve() == exclude_self.resolve():
            continue
        # Skip large files
        if max_size and path.stat().st_size > max_size:
            continue
        files.append(path)
    return files


def generate_structure(base_dir: Path, files: list[Path]) -> str:
    """Generate a simple tree-like folder structure for included files."""
    structure_lines = ["# ==============================================================",
                       "# 📁 Project Structure",
                       "# =============================================================="]
    for f in sorted(files):
        rel = f.relative_to(base_dir)
        depth = len(rel.parts) - 1
        indent = "  " * depth
        structure_lines.append(f"{indent}- {rel}")
    return "\n".join(structure_lines)


# ---------------------------------------------------------------------
# 📦 Export logic
# ---------------------------------------------------------------------
def export_source_code(base_dir: Path, output_file: Path, max_size: int | None):
    """Export all Python source files (excluding ignored/system/self)."""
    print(f"🔍 Scanning Python files in: {base_dir}")

    gitignore_path = base_dir / ".gitignore"
    patterns = load_gitignore_patterns(gitignore_path)
    this_file = Path(__file__).resolve()
    files = collect_python_files(base_dir, patterns, exclude_self=this_file, max_size=max_size)

    print(f"📦 Found {len(files)} Python files to export")

    with open(output_file, "w", encoding="utf-8") as out:
        # Write structure first
        structure = generate_structure(base_dir, files)
        out.write(structure + "\n\n")

        # Write source files
        for fpath in sorted(files):
            rel = fpath.relative_to(base_dir)
            out.write(f"\n\n# ==============================================================\n")
            out.write(f"# 📄 {rel}\n")
            out.write(f"# ==============================================================\n\n")
            try:
                content = fpath.read_text(encoding="utf-8")
                out.write(content)
            except Exception as e:
                out.write(f"# ⚠️ Failed to read {rel}: {e}\n")

    print(f"\n✅ Exported {len(files)} files → {output_file.resolve()}")


# ---------------------------------------------------------------------
# 🚀 CLI Entry
# ---------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export all Python source files into a single text file.")
    parser.add_argument("--path", type=str, default=".", help="Path to the project/folder to scan (default: current directory)")
    parser.add_argument("--out", type=str, default="source_code.txt", help="Output file path (default: source_code.txt)")
    parser.add_argument("--max-size", type=int, default=None, help="Maximum file size in bytes to include (default: no limit)")
    args = parser.parse_args()

    base_dir = Path(args.path).resolve()
    output_file = Path(args.out).resolve()

    export_source_code(base_dir, output_file, max_size=args.max_size)

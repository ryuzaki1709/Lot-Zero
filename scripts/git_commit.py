"""Script to initialize git repository and commit project files using Dulwich."""

import os
from pathlib import Path
from dulwich import porcelain
from dulwich.repo import Repo

ROOT = Path(__file__).resolve().parent.parent

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".pytest_cache",
    ".pytest-tmp",
    ".pytest-tmp-review",
    ".hypothesis",
    ".ruff_cache",
    "dist",
    "__pycache__",
    ".turbo",
    ".next",
    ".vite",
}

IGNORED_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".log",
}


def get_trackable_files(root: Path) -> list[str]:
    files_to_add: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in-place
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")]

        rel_dir = Path(dirpath).relative_to(root)
        if any(part in IGNORED_DIRS for part in rel_dir.parts):
            continue

        for filename in filenames:
            ext = Path(filename).suffix
            if ext in IGNORED_EXTENSIONS:
                continue
            if filename.startswith(".") and filename != ".gitignore":
                continue
            full_path = Path(dirpath) / filename
            rel_path = full_path.relative_to(root).as_posix()
            files_to_add.append(rel_path)
    return files_to_add


def commit_all(message: str):
    repo_dir = str(ROOT)

    # 1. Initialize repository if .git doesn't exist
    if not (ROOT / ".git").exists():
        repo = Repo.init(repo_dir)
        print(f"Initialized empty Git repository in {repo_dir}")
    else:
        repo = Repo(repo_dir)
        print(f"Opened existing Git repository in {repo_dir}")

    # Remove stale index.lock if present from prior aborted attempt
    lock_file = ROOT / ".git" / "index.lock"
    if lock_file.exists():
        lock_file.unlink()

    # 2. Get and stage trackable files
    files = get_trackable_files(ROOT)
    print(f"Found {len(files)} source and config files to track.")
    
    porcelain.add(repo_dir, paths=files)
    print(f"Staged {len(files)} files into Git index.")

    # 3. Commit
    commit_sha = porcelain.commit(
        repo_dir,
        message=message.encode("utf-8"),
        author="Lot Zero <agent@lot-zero.local>".encode("utf-8"),
        committer="Lot Zero <agent@lot-zero.local>".encode("utf-8"),
    )
    print(f"Committed checkpoint: {commit_sha.decode('utf-8')[:10]} - {message}")

    # 4. Verify log
    log_entries = porcelain.log(repo_dir, max_entries=5)
    for entry in log_entries:
        c = entry.commit
        print(f"Commit: {c.id.decode('utf-8')[:8]} | {c.message.decode('utf-8').strip()}")


if __name__ == "__main__":
    commit_all("feat: Complete Lot Zero with SQLite event store, API key auth, read models, audit export, and dashboard")

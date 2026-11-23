import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise GitError(message or f"git {args[0]} failed ({result.returncode})")
    return result.stdout.decode("utf-8", errors="surrogateescape")


class GitRepository:
    def __init__(self, path: Path) -> None:
        self.path = Path(_git(path, "rev-parse", "--show-toplevel").strip()).resolve()

    def commit_sha(self, revision: str = "HEAD") -> str:
        return _git(self.path, "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}").strip()

    def open_worktree(self, path: Path, branch_ref: str, commit_sha: str, *, legacy_path: Path | None = None) -> Path:
        if not branch_ref.startswith("refs/heads/"):
            raise ValueError("Use a full branch ref under refs/heads/")
        _git(self.path, "check-ref-format", branch_ref)
        path = path.resolve()
        name = branch_ref.removeprefix("refs/heads/")
        expected = self.commit_sha(commit_sha)
        exists = branch_ref in _git(self.path, "for-each-ref", "--format=%(refname)", branch_ref).splitlines()
        if exists and self.commit_sha(branch_ref) != expected:
            raise GitError(f"{branch_ref} no longer points to saved commit {expected}")

        worktrees = self._worktree_branches()
        checked_out = next((directory for directory, ref in worktrees.items() if ref == branch_ref), None)
        if checked_out is not None and checked_out != path:
            if legacy_path is None or checked_out != legacy_path.resolve() or path.exists():
                raise GitError(f"{branch_ref} is already checked out at {checked_out}")
            if checked_out.exists():
                _git(self.path, "worktree", "move", "--", str(checked_out), str(path))
                return path

        if path in worktrees and (path / ".git").is_file():
            if worktrees[path] == branch_ref:
                return path
            if _git(path, "status", "--porcelain", "--untracked-files=normal"):
                raise GitError("The work item checkout has uncommitted changes. Save them before changing branches.")
            branch = (name,) if exists else ("-c", name, expected)
            _git(path, "switch", "--no-overwrite-ignore", *branch)
        else:
            branch = () if exists else ("-b", name)
            recreate = ("--force",) if path in worktrees or checked_out is not None else ()
            _git(self.path, "worktree", "add", *recreate, *branch, "--", str(path), name if exists else expected)
        return path

    def _worktree_branches(self) -> dict[Path, str | None]:
        listing = _git(self.path, "worktree", "list", "--porcelain", "-z")
        worktrees = {}
        for entry in listing.split("\0\0"):
            fields = entry.split("\0")
            if fields[0].startswith("worktree "):
                path = Path(fields[0].removeprefix("worktree ")).resolve()
                worktrees[path] = next((field.removeprefix("branch ") for field in fields if field.startswith("branch ")), None)
        return worktrees

    def save_commit(self, worktree: Path, message: str) -> str:
        _git(worktree, "add", "-A")
        if _git(worktree, "diff", "--cached", "--name-only", "--"):
            _git(worktree, "commit", "-m", message)
        return _git(worktree, "rev-parse", "HEAD").strip()

    def diff(self, base: str, result: str) -> str:
        return _git(self.path, "diff", "--binary", "--no-color", "--no-ext-diff", "--no-textconv",
                    self.commit_sha(base), self.commit_sha(result), "--")

    def read_text_file(self, revision: str, path: str) -> str:
        parts = path.split("/")
        if "\\" in path or any(ord(char) < 32 for char in path) or any(
            part.casefold() in {"", ".", "..", ".git", ".env"} or part.casefold().startswith(".env.")
            for part in parts
        ):
            raise ValueError("Choose a repository-relative file path.")
        spec = f"{self.commit_sha(revision)}:{path}"
        try:
            size = int(_git(self.path, "cat-file", "-s", spec))
            if size > 256 * 1024:
                raise ValueError("This file is too large to preview.")
            content = _git(self.path, "cat-file", "blob", spec)
        except GitError as exc:
            raise LookupError("This file is unavailable in the saved commit.") from exc
        if "\0" in content or any(0xDC80 <= ord(char) <= 0xDCFF for char in content):
            raise ValueError("Only UTF-8 text files can be previewed.")
        return content

    def merge(self, worktree: Path, revision: str) -> str:
        _git(worktree, "merge", "--no-edit", "--", self.commit_sha(revision))
        return _git(worktree, "rev-parse", "HEAD").strip()

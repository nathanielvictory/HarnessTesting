import subprocess
from dataclasses import dataclass
from functools import cached_property
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory


class GitError(RuntimeError):
    pass


@dataclass(frozen=True)
class FileChange:
    status: str
    old_path: str | None
    new_path: str | None
    old_mode: str
    new_mode: str
    old_object: str
    new_object: str


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
            raise GitError(f"{branch_ref} no longer points to commit {expected}")

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

    def changed_files(self, base: str, result: str) -> list[FileChange]:
        raw = _git(self.path, "diff", "--raw", "-z", "--no-abbrev", "--find-renames", "--no-color", "--no-ext-diff",
                   self.commit_sha(base), self.commit_sha(result), "--")
        fields = iter(raw.split("\0")[:-1])
        changes = []
        for header in fields:
            old_mode, new_mode, old_object, new_object, status = header[1:].split()
            path = _json_text(next(fields))
            new_path = _json_text(next(fields)) if status[0] in "RC" else path
            changes.append(FileChange(
                status[0],
                None if status == "A" else path,
                None if status == "D" else new_path,
                old_mode, new_mode, old_object, new_object,
            ))
        return changes

    def file_diff(self, change: FileChange) -> dict[str, str | bool]:
        if change.old_path is not None and change.new_path is not None and "160000" not in (
            change.old_mode, change.new_mode,
        ):
            patch = _git(self.path, "diff", "--patch", "--unified=3", "--no-color", "--no-ext-diff", "--no-textconv",
                         change.old_object, change.new_object, "--")
            binary = any(line.startswith("Binary files ") for line in patch.split("\n"))
            return {"patch": _json_text(patch), "binary": binary}

        before = self._diff_side(change.old_mode, change.old_object)
        after = self._diff_side(change.new_mode, change.new_object)
        if any("\0" in text or text != _json_text(text) for text in (before, after)):
            return {"binary": True}
        return {"before": before, "after": after, "binary": False}

    def _diff_side(self, mode: str, object_id: str) -> str:
        if mode == "000000":
            return ""
        if mode == "160000":
            return f"Subproject commit {object_id}\n"
        return _git(self.path, "cat-file", "blob", object_id)

    @staticmethod
    def is_readable_path(path: str) -> bool:
        parts = path.split("/")
        return not ("\\" in path or any(ord(char) < 32 for char in path) or any(
            part.casefold() in {"", ".", "..", ".git", ".env"} or part.casefold().startswith(".env.")
            for part in parts
        ))

    def read_text_file(self, revision: str, path: str) -> str:
        if not self.is_readable_path(path):
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

    def integrate(self, item_id: int, base: str, revisions: list[str], *, final: bool = False) -> str:
        """Merge saved snapshots without touching the developer's checkout or step branches."""
        base = self.commit_sha(base)
        commits = list(dict.fromkeys(self.commit_sha(ref) for ref in revisions))
        digest = sha256(' '.join([base, *commits]).encode()).hexdigest()
        cache_ref = f'refs/harness/integrations/{item_id}/{digest}'
        known = _git(self.path, 'for-each-ref', '--format=%(objectname)', cache_ref).strip()
        if known:
            result = known
        elif not commits or commits == [base]:
            result = base
        else:
            with TemporaryDirectory(prefix='harness-integrate-') as directory:
                checkout = Path(directory) / 'checkout'
                _git(self.path, 'worktree', 'add', '--detach', '--', str(checkout), base)
                try:
                    for commit in commits:
                        _git(checkout, 'merge', '--no-edit', '--', commit)
                    result = _git(checkout, 'rev-parse', 'HEAD').strip()
                    _git(self.path, 'update-ref', cache_ref, result)
                except GitError as exc:
                    raise GitError(f'Could not integrate saved work: {exc}') from exc
                finally:
                    _git(self.path, 'worktree', 'remove', '--force', '--', str(checkout))
        if final:
            _git(self.path, 'update-ref', f'refs/harness/results/{item_id}', result)
        return result

class GitWorkspace:
    def __init__(self, repository_path: Path, worktrees: Path, item_id: int, title: str | None) -> None:
        self.repository_path = repository_path
        self.worktrees = worktrees
        self.checkout = worktrees / 'items' / str(item_id)
        self.item_id = item_id
        self.title = title

    @cached_property
    def repository(self) -> GitRepository:
        return GitRepository(self.repository_path)

    def prepare(self, node_id: int, branch_ref: str | None, commit_sha: str) -> tuple[Path, str]:
        self.checkout.parent.mkdir(parents=True, exist_ok=True)
        branch_ref = branch_ref or f'refs/heads/harness/{self.item_id}-{node_id}'
        path = self.repository.open_worktree(self.checkout, branch_ref, commit_sha,
                                            legacy_path=self.worktrees / str(node_id))
        return path, branch_ref

    def save(self) -> str:
        return self.repository.save_commit(self.checkout, self.title or f'Work item {self.item_id}')

def _json_text(text: str) -> str:
    return text.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace")

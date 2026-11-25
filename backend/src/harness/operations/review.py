from dataclasses import dataclass

from pydantic_ai import ModelRetry, Tool

from harness.git.repository import FileChange
from harness.graph.node import Node, NodeData


@dataclass(kw_only=True)
class ReviewData(NodeData):
    pass


class Review(Node[ReviewData]):
    node_type = 'human_review'
    data_type = ReviewData

    def initial_prompt(self, message: str) -> tuple[str, str]:
        instructions = (
            'Discuss the completed step with the user and identify what still needs verification. '
            'Use list_changed_files and get_file_diff to inspect changes. '
            'Use the repository read tools when you need surrounding code.'
        )
        prompt = 'Review the saved result.'
        if summary := self.state.data.summary:
            prompt += f'\n\nSummary\n{summary}'
        if message:
            prompt += f'\n\nRequest\n{message}'
        return instructions, prompt

    def model_tools(self) -> tuple[str | Tool[None], ...]:
        return 'read_file', 'list_files', 'grep', Tool(self.list_changed_files), Tool(self.get_file_diff)

    def list_changed_files(self) -> list[dict[str, str | None]]:
        """List repository paths and change statuses for the saved implementation under review."""
        return [{'status': change.status, 'old_path': change.old_path, 'new_path': change.new_path}
                for change in self._changed_files()]

    def get_file_diff(self, path: str) -> dict[str, str | bool]:
        """Read a saved diff by its new path, or by its old path if the file was deleted."""
        for change in self._changed_files():
            if (change.new_path or change.old_path) == path:
                return self.graph.workspace.repository.file_diff(change)
        raise ModelRetry('Choose a path returned by list_changed_files.')

    def _changed_files(self) -> list[FileChange]:
        source = self.graph.creation_edge(self).source
        repository = self.graph.workspace.repository
        return [change for change in repository.changed_files(source.state.commit_sha, self.state.commit_sha)
                if all(repository.is_readable_path(path) for path in (change.old_path, change.new_path)
                       if path is not None)]

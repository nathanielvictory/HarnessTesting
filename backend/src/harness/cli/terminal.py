import sys
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from queue import Empty, SimpleQueue
from time import sleep

from pydantic_ai import CancellationToken

from harness.agents.harness import AgentTurn


class Quit(Exception):
    pass


class Terminal:
    def show(self, message: str = "") -> None:
        print(message, flush=True)

    def ask(self, prompt: str) -> str:
        try:
            return input(prompt).strip()
        except EOFError as exc:
            raise Quit from exc

    def choose(self, heading: str, choices: Sequence[tuple[str, str]]) -> str:
        self.show(f"\n{heading}")
        for index, (_, label) in enumerate(choices, 1):
            self.show(f"  {index}. {label}")
        self.show("  q. Quit")
        while True:
            answer = self.ask("> ")
            if answer.lower() == "q":
                raise Quit
            if answer.isdecimal() and 1 <= int(answer) <= len(choices):
                return choices[int(answer) - 1][0]
            self.show("Choose a number from the list, or q to quit.")

    def wait_for_agent(
        self, run: Callable[[Callable[[str], None], CancellationToken], AgentTurn], show_graph: Callable[[], None]
    ) -> AgentTurn:
        quiet = SimpleQueue[str]()
        token = CancellationToken()
        seen: set[str] = set()
        controls = " G: graph · Q: save and quit." if sys.stdin.isatty() else " Ctrl+C: save and quit."
        self.show(f"Agent working.{controls}")
        with _keyboard() as key, ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run, quiet.put, token)
            try:
                while not future.done():
                    try:
                        tool = quiet.get_nowait()
                    except Empty:
                        pass
                    else:
                        if tool not in seen:
                            seen.add(tool)
                            self.show(f"  Agent: {tool.replace('_', ' ')}")
                    choice = key()
                    if choice and choice.lower() == "g":
                        show_graph()
                    elif choice and choice.lower() == "q":
                        raise KeyboardInterrupt
                    sleep(0.1)
            except KeyboardInterrupt:
                self.show("Saving before quitting…")
                token.cancel()
            except BaseException:
                token.cancel()
                raise
            result = future.result()
            return replace(result, paused=True) if token.cancelled else result


@contextmanager
def _keyboard() -> Iterator[Callable[[], str | None]]:
    if not sys.stdin.isatty():
        yield lambda: None
    elif sys.platform == "win32":
        import msvcrt

        yield lambda: msvcrt.getwch() if msvcrt.kbhit() else None
    else:
        import select
        import termios
        import tty

        fd = sys.stdin.fileno()
        saved = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        try:
            yield lambda: sys.stdin.read(1) if select.select([fd], [], [], 0)[0] else None
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, saved)

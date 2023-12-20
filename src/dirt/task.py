from typing import List


class Task:
    def __init__(self, name: str, consumes: List[str], produces: List[str]):
        self.name = name
        self.consumes = consumes
        self.produces = produces

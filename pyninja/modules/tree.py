from pathlib import Path
from typing import List


class Tree:
    """Root tree formatter for a particular directory location.

    This class allows the creation of a visual representation of the file
    system hierarchy of a specified directory. It can optionally skip files
    that start with a dot (hidden files).

    >>> Tree

    """

    def __init__(self, skip_dot_files: bool):
        """Instantiates the tree object.

        Args:
            skip_dot_files (bool): If True, skips files with a dot prefix (hidden files).
        """
        self.tree_text = []
        self.skip_dot_files = skip_dot_files

    def scan(self, path: Path, last: bool = True, header: str = "") -> List[str]:
        """Returns contents for a folder as a root tree.

        Args:
            path: Directory path for which the root tree is to be extracted.
            last: Indicates if the current item is the last in the directory.
            header: The prefix for the current level in the tree structure.

        Returns:
            List[str]: A list of strings representing the directory structure.
        """
        elbow = "└──"
        pipe = "│  "
        tee = "├──"
        blank = "   "
        self.tree_text.append(header + (elbow if last else tee) + path.name)
        if path.is_dir():
            children = list(path.iterdir())
            for idx, child in enumerate(children):
                # Skip child file/directory when dot files are supposed to be hidden
                if self.skip_dot_files and child.name.startswith("."):
                    continue
                self.scan(
                    child,
                    header=header + (blank if last else pipe),
                    last=idx == len(children) - 1,
                )
        return self.tree_text

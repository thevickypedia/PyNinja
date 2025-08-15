from typing import Optional

from pydantic import BaseModel, DirectoryPath, FilePath, PositiveFloat, PositiveInt


class RunCommand(BaseModel):
    """Payload for run-command endpoint.

    >>> RunCommand

    """

    command: str
    timeout: PositiveInt | PositiveFloat = 3
    stream: bool = False


class ListFiles(BaseModel):
    """Payload for list-files endpoint.

    >>> ListFiles

    """

    directory: DirectoryPath
    show_hidden_files: bool = False
    include_directories: bool = True
    deep_scan: bool = False


class GetFile(BaseModel):
    """Payload for get-file endpoint.

    >>> GetFile

    """

    filepath: FilePath


class DeleteContent(BaseModel):
    """Payload for delete-file endpoint.

    >>> DeleteContent

    """

    filepath: Optional[FilePath] = None
    directory: Optional[DirectoryPath] = None
    recursive: bool = False

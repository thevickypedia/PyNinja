import os
import pathlib
import shutil
import zipfile


def archive(path: pathlib.Path, directory: pathlib.Path) -> pathlib.Path:
    """Archives a file or directory into a zip file.

    Args:
        path: Path to the file or directory to be archived.
        directory: Directory where the zip file will be created.

    Returns:
        pathlib.Path:
        The path to the created zip file.
    """
    zip_file = directory / f"{path.stem}.zip"
    with zipfile.ZipFile(zip_file, "w", zipfile.ZIP_DEFLATED) as zipf:
        if path.is_dir():
            for root, _, files in os.walk(path):
                for file in files:
                    file_path = pathlib.Path(root) / file
                    arcname = file_path.relative_to(path.parent)
                    zipf.write(file_path, arcname=arcname)
        else:
            zipf.write(path, arcname=path.name)
    return zip_file


def unarchive(zip_file: str | pathlib.Path, directory: str | pathlib.Path) -> str:
    """Unarchives a zip file into a specified directory.

    Args:
        zip_file: Zip file to be unarchived.
        directory: Directory where the contents will be extracted.

    Returns:
        str:
        The path to the directory containing the unzipped content.
    """
    shutil.unpack_archive(zip_file, directory)
    return os.path.join(directory, os.path.basename(zip_file))

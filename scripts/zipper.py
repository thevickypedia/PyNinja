import os
import pathlib
import shutil
import zipfile


def archive(
    path: pathlib.Path, directory: pathlib.Path = pathlib.Path(__file__).parent
) -> pathlib.Path:
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


def unarchive(
    zip_file: pathlib.Path, directory: pathlib.Path = pathlib.Path(__file__).parent
) -> pathlib.Path:
    """Unarchives a zip file into a specified directory.

    Args:
        zip_file: Zip file to be unarchived.
        directory: Directory where the contents will be extracted.

    Returns:
        pathlib.Path:
        The path to the directory containing the unzipped content.
    """
    if not zip_file.exists():
        raise FileNotFoundError(f"Zip file {zip_file} does not exist.")
    if zip_file.suffix not in [".zip", ".tar", ".tar.gz", ".tar.bz2"]:
        raise ValueError(
            "Unsupported archive format. Only .zip, .tar, .tar.gz, and .tar.bz2 are supported."
        )
    # Create a destination directory for unzipped content
    directory.mkdir(parents=True, exist_ok=True)
    shutil.unpack_archive(zip_file, directory)
    return directory / zip_file.stem

from egnyte_client.operations.generic import Operation, normalize_path, query
from egnyte_client.schemas.insights import RecentFile, RecentFiles

# -----------------------------------------------------------------------------
# OPERATION: list_recent_files
# -----------------------------------------------------------------------------


def list_recent_files(*, folder_path: str | None = None) -> Operation[list[RecentFile]]:
    """
    Build the caller's recently accessed files, optionally within one folder.

    Returns:
        Operation[list[RecentFile]]: The list recent files operation.
    """
    return Operation(
        method="GET",
        path="/v1/insights/files",
        params=query(folder_path=normalize_path(folder_path) if folder_path else None),
        parse=lambda response: (
            RecentFiles.model_validate_json(response.content).recent_files
        ),
    )

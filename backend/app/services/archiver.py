"""ZIP archive creation from renamed document files."""

import io
import zipfile


def create_zip(files: dict[str, bytes]) -> bytes:
    """Create a ZIP archive from a mapping of filename -> PDF bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(filename, content)
    return buffer.getvalue()

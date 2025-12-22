import os
import shutil
import uuid
from fastapi import UploadFile
from pathlib import Path
from typing import List

from src.core.config import settings

# Đảm bảo thư mục tmp tồn tại
TMP_DIR = Path(settings.tmp_dir)
TMP_DIR.mkdir(exist_ok=True)

async def save_upload_files(files: List[UploadFile]) -> List[str]:
    """
    Lưu các file upload vào thư mục tmp và trả về danh sách đường dẫn.
    Chỉ chấp nhận image (jpg, jpeg, png).
    """
    saved_paths: List[str] = []
    
    for file in files:
        if file.content_type not in ["image/jpeg", "image/jpg", "image/png"]:
            raise ValueError(f"File {file.filename} không phải là hình ảnh hợp lệ (chỉ chấp nhận jpg/png)")

        # Tạo tên file unique để tránh trùng
        file_extension = Path(file.filename).suffix.lower()
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = TMP_DIR / unique_filename

        # Lưu file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        saved_paths.append(str(file_path))
    
    return saved_paths

def cleanup_files(file_paths: List[str]):
    """Xóa các file tạm sau khi dùng xong (gọi khi hoàn thành hoặc lỗi)"""
    for path in file_paths:
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"Error deleting file {path}: {e}")
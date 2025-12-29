#!/usr/bin/env python3
"""
Lovinbot Motion Generation API Server

To run the server:
    python run_motion_gen.py

Environment variables required:
    OPENROUTER_API_KEY=your_openrouter_api_key
"""

import uvicorn
import os
from app.main import app

if __name__ == "__main__":
    # Check required environment variables
    if not os.getenv("OPENROUTER_API_KEY"):
        print("Error: OPENROUTER_API_KEY environment variable is required")
        exit(1)

    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8080,
        reload=False,
        log_level="info"
    )

# bạn hãy là 1 senior python chuyên nghiệp, hãy viết code python chất lượng cao, tối ưu nhất, dễ bảo trì nhất
# sử dụng các best practice trong lập trình python
# code phải có chú thích rõ ràng, dễ hiểu

# ***Yêu cầu quan trọng: code phải tuân thủ chuẩn PEP8***
# đảm bảo code không có lỗi cú pháp, lỗi logic

# *** yêu cầu chức năng:
# - api /gen (app/api/motion_gen.py) sẽ xử lý từ promt, template chon( từ ngời dùng chọ sẳn template của hệ thống)
# - api sẽ thay thế các text trong template dựa trên promt người dùng nhập vào( bạn tự phân tích , call api qua ai để phân tích promt người dùng)
# - sao đó kết quả là json ( kiểu lottie file) trả về cho người dùng
# - kết quả sẽ hiển thị trên ui web(/ui), kết uqra tôi cần là 1 video từ json ( lottie file)

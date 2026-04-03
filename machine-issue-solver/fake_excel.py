#!/usr/bin/env python3
"""
Generate fake Excel file for testing import_excel.py
Usage: python fake_excel.py [output_file.xlsx] [--rows 100]
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path
import random

from faker import Faker
from openpyxl import Workbook

fake = Faker()

# Sample data pools
LINES = list(range(1, 6))  # 1, 2, 3, 4, 5 (integers, will be saved as strings in Excel)
TEAMS = ["Team Alpha", "Team Beta", "Team Gamma", "Team Delta"]
MACHINES = [f"Machine-{i:03d}" for i in range(1, 21)]  # Machine-001 to Machine-020
LOCATIONS = ["Zone A", "Zone B", "Zone C", "Building 1", "Building 2", None]
SERIALS = [f"SN{random.randint(10000, 99999)}" for _ in range(30)] + [None] * 10

HIEN_TUONG = [
    "Máy không khởi động được",
    "Băng tải bị kẹt",
    "Robot không pick đúng vị trí",
    "Máy hàn bị lỗi điểm hàn",
    "CNC bị lệch tọa độ",
    "Máy nén bị rò rỉ khí",
    "Bộ điều khiển PLC lỗi",
    "Cảm biến không nhận tín hiệu",
    "Máy dừng đột ngột",
    "Quá nhiệt",
    "Rò rỉ dầu",
    "Bơm hỏng",
    "Van khí lỗi",
    "Mất điện",
    "Lỗi chương trình",
]

NGUYEN_NHAN = [
    "Hỏng cảm biến vị trí",
    "Dây đai băng tải bị đứt",
    "Lỗi chương trình điều khiển",
    "Hết dầu bôi trơn",
    "Nhiệt độ cao quá mức",
    "Bụi bẩn bám vào board mạch",
    "Lỗi nguồn điện cung cấp",
    "Tuổi thọ thiết bị hết hạn",
    "Vận hành sai quy trình",
    "Bảo trì không định kỳ",
]

KHAC_PHUC = [
    "Thay cảm biến mới",
    "Thay dây đai, căn chỉnh lại",
    "Reload chương trình, calibrate",
    "Bơm dầu bôi trơn định kỳ",
    "Vệ sinh tản nhiệt, kiểm tra quạt",
    "Vệ sinh board mạch bằng cồn",
    "Kiểm tra nguồn 24V, thay nguồn",
    "Thay thế linh kiện",
    "Hiệu chỉnh lại thông số",
    "Gọi nhà cung cấp kiểm tra",
]

PICS = ["Mr. A", "Mr. B", "Ms. C", "Mr. D", "Engineer 1", "Engineer 2", "Technician 1", "Technician 2"]


def random_date():
    """Generate random date in last year."""
    start = datetime(2023, 1, 1)
    end = datetime(2024, 12, 31)
    delta = end - start
    random_days = random.randint(0, delta.days)
    return start + timedelta(days=random_days)


def generate_excel(output_path: str, num_rows: int = 100):
    """Generate Excel file with fake data."""
    print(f"📝 Generating {num_rows} rows...")
    
    wb = Workbook()
    ws = wb.active
    ws.title = "Issues"
    
    # Headers
    headers = [
        "STT", "Line", "Team", "Machine", "Location", "Serial", 
        "Date", "Start Time", "Stop Time", "Total Time", "Week", "Year",
        "Hiện tượng", "Nguyên nhân", "Khắc phục", "PIC", "User Input"
    ]
    ws.append(headers)
    
    # Data rows
    for i in range(1, num_rows + 1):
        date_obj = random_date()
        has_location = random.random() > 0.3  # 70% có location
        has_serial = random.random() > 0.4    # 60% có serial
        
        row = [
            i,  # STT
            random.choice(LINES),
            random.choice(TEAMS),
            random.choice(MACHINES),
            random.choice(LOCATIONS) if has_location else None,
            random.choice(SERIALS) if has_serial else None,
            date_obj.strftime("%Y-%m-%d"),
            f"{random.randint(6, 22):02d}:{random.randint(0, 59):02d}",  # Start Time
            f"{random.randint(6, 22):02d}:{random.randint(0, 59):02d}",  # Stop Time
            f"{random.randint(5, 180)} min",  # Total Time
            date_obj.isocalendar()[1],  # Week
            date_obj.year,  # Year
            random.choice(HIEN_TUONG),
            random.choice(NGUYEN_NHAN),
            random.choice(KHAC_PHUC),
            random.choice(PICS),
            fake.sentence(),
        ]
        ws.append(row)
        
        if i % 20 == 0:
            print(f"   Progress: {i}/{num_rows}")
    
    # Save
    wb.save(output_path)
    print(f"✅ Saved to: {output_path}")
    print(f"   Total rows: {num_rows} (plus 1 header)")


def main():
    parser = argparse.ArgumentParser(description="Generate fake Excel for testing")
    parser.add_argument("output", nargs="?", default="test_data.xlsx", help="Output file path")
    parser.add_argument("--rows", type=int, default=100, help="Number of data rows (default: 100)")
    
    args = parser.parse_args()
    
    generate_excel(args.output, args.rows)


if __name__ == "__main__":
    main()

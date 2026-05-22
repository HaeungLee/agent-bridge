import re
from pathlib import Path

def parse_pb(file_path: Path):
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return
        
    print(f"Reading file: {file_path} (Size: {file_path.stat().st_size} bytes)")
    data = file_path.read_bytes()
    
    # Extract readable UTF-8 strings
    # We look for printable ASCII/UTF-8 character sequences of length >= 4
    strings = []
    current = bytearray()
    for b in data:
        if 32 <= b <= 126 or b in (9, 10, 13) or b >= 128:  # Printable and UTF-8 continuation bytes
            current.append(b)
        else:
            if len(current) >= 4:
                try:
                    decoded = current.decode('utf-8', errors='ignore').strip()
                    if decoded:
                        strings.append(decoded)
                except Exception:
                    pass
            current = bytearray()
            
    if len(current) >= 4:
        try:
            decoded = current.decode('utf-8', errors='ignore').strip()
            if decoded:
                strings.append(decoded)
        except Exception:
            pass
            
    print(f"\n--- End of File Safe ASCII Dump (Last 5000 bytes) ---")
    chunk_size = 5000
    if len(data) > chunk_size:
        subset = data[-chunk_size:]
    else:
        subset = data
        
    # Print in blocks of 80 characters for readability
    lines = []
    current_line = []
    for b in subset:
        if 32 <= b <= 126:
            current_line.append(chr(b))
        elif b in (10, 13):
            current_line.append(" ") # replace newlines with space
        else:
            current_line.append(".")
            
        if len(current_line) >= 80:
            lines.append("".join(current_line))
            current_line = []
            
    if current_line:
        lines.append("".join(current_line))
        
    for idx, line in enumerate(lines[-50:]):  # Print the last 50 lines
        print(f"{idx:02d}: {line}")

if __name__ == "__main__":
    pb_file = Path(r"C:\Users\Harry\.gemini\antigravity-cli\conversations\d9ed13c0-2028-4b36-8460-1125b019ffd7.pb")
    parse_pb(pb_file)

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
            
    print(f"\n--- Extracted Strings (Total: {len(strings)}) ---")
    for idx, s in enumerate(strings):
        # Strip non-ASCII to prevent terminal print errors
        ascii_only = s.encode('ascii', errors='ignore').decode('ascii').strip()
        if "AGENT_BRIDGE" in ascii_only:
            print(f"Found match: {repr(ascii_only)}")

if __name__ == "__main__":
    pb_file = Path(r"C:\Users\Harry\.gemini\antigravity-cli\conversations\d9ed13c0-2028-4b36-8460-1125b019ffd7.pb")
    parse_pb(pb_file)

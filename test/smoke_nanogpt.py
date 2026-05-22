#!/usr/bin/env python3
import os
import json
import urllib.request
import urllib.error
import time
from pathlib import Path

# Color codes for clean output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def load_env(env_path: Path):
    """Loads environment variables from a .env file without external dependencies."""
    if not env_path.exists():
        return
    
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip()

def test_model(model_name: str, api_key: str) -> bool:
    print(f"\n{BLUE}[Testing]{RESET} Model: {model_name}")
    
    url = "https://api.nano-gpt.com/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    data = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": "Say 'API Active' in one short sentence."}
        ],
        "max_tokens": 30
    }
    
    req_body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=req_body, headers=headers, method="POST")
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            res_body = response.read().decode("utf-8")
            elapsed = time.time() - start_time
            
            res_data = json.loads(res_body)
            choices = res_data.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "").strip()
                print(f"  {GREEN}[OK] Success!{RESET} (Time: {elapsed:.2f}s)")
                print(f"  {GREEN}Response:{RESET} {content}")
                return True
            else:
                print(f"  {RED}[FAIL] Failed:{RESET} No choices returned. Raw response: {res_body}")
                return False
                
    except urllib.error.HTTPError as e:
        elapsed = time.time() - start_time
        try:
            error_body = e.read().decode("utf-8")
            error_data = json.loads(error_body)
            error_msg = error_data.get("error", {}).get("message", error_body)
        except Exception:
            error_msg = f"HTTP Status {e.code}"
            error_body = ""
            
        print(f"  {RED}[FAIL] HTTP Error {e.code}:{RESET} {error_msg} (Time: {elapsed:.2f}s)")
        if error_body:
            print(f"  {YELLOW}Raw Error Details:{RESET} {error_body}")
        return False
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  {RED}[FAIL] Error:{RESET} {e} (Time: {elapsed:.2f}s)")
        return False

def main():
    root_dir = Path(__file__).resolve().parent
    env_path = root_dir / ".env"
    
    # Try loading from .env
    load_env(env_path)
    
    api_key = os.environ.get("NANOGPT_API_KEY")
    if not api_key or api_key == "your_nanogpt_api_key_here":
        print(f"{RED}Error: NANOGPT_API_KEY is not configured!{RESET}")
        print(f"Please copy {YELLOW}.env.example{RESET} to {YELLOW}.env{RESET} and populate it with your actual nanoGPT API Key.")
        print(f"File location: {env_path}")
        return 1
        
    print(f"{GREEN}============================================")
    print(f" Starting nanoGPT API Direct Smoke Test")
    print(f"============================================{RESET}")
    print(f"Loaded API Key: {api_key[:6]}...{api_key[-4:] if len(api_key) > 10 else ''}")
    
    # Models to test
    models_to_test = [
        "deepseek/deepseek-v4-pro",
        "nano-gpt/deepseek/deepseek-v4-pro",
        "deepseek/deepseek-v4-flash",
        "nano-gpt/deepseek/deepseek-v4-flash",
        "xiaomi/mimo-v2.5-pro",
    ]
    
    results = {}
    for model in models_to_test:
        results[model] = test_model(model, api_key)
        
    print(f"\n{GREEN}============================================")
    print(f" Test Summary")
    print(f"============================================{RESET}")
    for model, success in results.items():
        status = f"{GREEN}PASS{RESET}" if success else f"{RED}FAIL{RESET}"
        print(f"- {model:<40}: {status}")
        
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())

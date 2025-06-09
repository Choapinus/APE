import argparse
import base64
import httpx
import sys
from pathlib import Path

DEFAULT_API_URL = "http://localhost:8000/prompt/stream"

def encode_image_file(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def main():
    parser = argparse.ArgumentParser(description="CLI for ape agent (multimodal LLM)")
    parser.add_argument("--prompt", type=str, help="Text prompt", required=False)
    parser.add_argument("--image", type=str, help="Path to image file", required=False)
    parser.add_argument("--session-id", type=str, help="Session ID (for context)", required=False)
    parser.add_argument("--api-url", type=str, default=DEFAULT_API_URL, help="API URL for /prompt/stream endpoint")
    args = parser.parse_args()

    payload = {}
    if args.prompt:
        payload["text"] = args.prompt
    if args.image:
        image_path = Path(args.image)
        if not image_path.exists():
            print(f"Image file not found: {args.image}", file=sys.stderr)
            sys.exit(1)
        payload["image_base64"] = encode_image_file(args.image)
    if args.session_id:
        payload["session_id"] = args.session_id

    print(f"Sending request to {args.api_url}...\n", file=sys.stderr)
    with httpx.stream("POST", args.api_url, json=payload, timeout=None) as response:
        if response.status_code != 200:
            print(f"Error: {response.status_code} {response.reason_phrase}", file=sys.stderr)
            sys.exit(1)
        for chunk in response.iter_text():
            print(chunk, end="", flush=True)

if __name__ == "__main__":
    main() 
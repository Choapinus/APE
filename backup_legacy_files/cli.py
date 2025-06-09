import httpx
import sys
import uuid
from pathlib import Path
import base64

API_URL = "http://localhost:8000/prompt/stream"

def encode_image_from_path(path_str: str) -> str | None:
    path = Path(path_str)
    if not path.exists():
        print(f"Image file not found: {path_str}", file=sys.stderr)
        return None
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

def main():
    session_id = str(uuid.uuid4())
    print("--- APE Interactive CLI ---")
    print(f"Session ID: {session_id}")
    print("Type 'exit' or 'quit' to end the session.")
    print("To send an image, type 'image <path/to/image.jpg>' followed by your prompt.")
    print("-" * 20)

    image_b64 = None

    while True:
        try:
            prompt = input("> ")
            if prompt.lower() in ["exit", "quit"]:
                print("Ending session. Goodbye!")
                break
            
            payload = {"session_id": session_id}
            
            if prompt.lower().startswith("image "):
                parts = prompt.split(" ", 1)
                image_path_str = parts[1].strip()
                image_b64 = encode_image_from_path(image_path_str)
                if image_b64:
                    print(f"Image '{image_path_str}' loaded for the next prompt.", file=sys.stderr)
                    # This prompt was just to load the image, continue to the next input loop
                    # for the actual text prompt.
                    continue
                else:
                    # Image loading failed, stay in the loop
                    continue

            payload["text"] = prompt
            if image_b64:
                payload["image_base64"] = image_b64

            with httpx.stream("POST", API_URL, json=payload, timeout=None) as response:
                if response.status_code != 200:
                    print(f"\n[ERROR] {response.status_code} - {response.text}", file=sys.stderr)
                else:
                    for chunk in response.iter_text():
                        print(chunk, end="", flush=True)
                    print() # Newline after the full response
            
            # Reset image after it has been sent
            image_b64 = None

        except KeyboardInterrupt:
            print("\nEnding session. Goodbye!")
            break
        except Exception as e:
            print(f"\n[ERROR] An unexpected error occurred: {e}", file=sys.stderr)

if __name__ == "__main__":
    main() 
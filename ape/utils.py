import base64
from io import BytesIO
from PIL import Image
from loguru import logger

def decode_base64_image(image_base64: str) -> Image.Image:
    image_data = base64.b64decode(image_base64)
    return Image.open(BytesIO(image_data)).convert("RGB")

def encode_image_base64(image: Image.Image) -> str:
    buffered = BytesIO()
    image.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def setup_logger():
    logger.add("logs/app.log", rotation="1 MB", retention="10 days", level="INFO")
    logger.info("Logger initialized.") 
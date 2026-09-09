import io
from PIL import Image, ImageDraw
from pptx import Presentation
from app.services.provider_router import ProviderRouter
from app.services.image_quality import is_documentary_image
from app.services.storage import storage_service

im = Image.new('RGB', (300, 180), '#bca785')
ImageDraw.Draw(im).rectangle((40, 30, 240, 160), fill='#4d3928')
buf = io.BytesIO()
im.save(buf, format='PNG')
data = buf.getvalue()
print(f"im size: {len(data)}, is_doc: {is_documentary_image(data)}")

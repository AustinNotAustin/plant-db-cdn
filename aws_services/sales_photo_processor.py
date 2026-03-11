import asyncio
import hashlib
import hmac
import logging
import random
import os
import httpx

from io import BytesIO
from PIL import Image, ImageDraw

from aws_services.config import CALLBACK_SECRET, CDN_SALES_IMGS
from aws_services.sales_photo_schema import SalesPhotoBatchRequest, WebhookPayload, SalesPhotoItem

logger = logging.getLogger(__name__)


async def process_sales_photo_item(item: SalesPhotoItem, callback_url: str):
    """
    Simulates heavy image processing and fires a secure webhook.
    """
    item_id = item.item_id
    error_message = ""
    final_image_path = ""
    final_image_url = ""
    
    try:
        config = item.configuration
        source_url = config.get("source_photo_url")
        
        # Download the baseline stock image
        if source_url:
            async with httpx.AsyncClient() as client:
                resp = await client.get(source_url)
                resp.raise_for_status()
                base_img = Image.open(BytesIO(resp.content)).convert("RGB")
        else:
            # Fallback if no URL is provided
            base_img = Image.new("RGB", (800, 600), color=(73, 109, 137))
            
        # Apply configurations
        draw = ImageDraw.Draw(base_img)
        
        # Parse resizing
        target_width = config.get("target_width", base_img.width)
        target_height = config.get("target_height", base_img.height)
        if target_width != base_img.width or target_height != base_img.height:
            base_img = base_img.resize((target_width, target_height))
            draw = ImageDraw.Draw(base_img)
            
        # Apply text/watermarks
        watermark_text = config.get("watermark_text")
        if watermark_text:
            text_color = config.get("text_color", (255, 255, 255))
            draw.text((50, 50), watermark_text, fill=text_color)
            
        label_text = config.get("label_text")
        if label_text:
            draw.text((50, base_img.height - 100), label_text, fill=(200, 200, 200))
            
        # Save the final assembled JPG
        mock_filename = f"composed_{item_id}_{random.randint(1000, 9999)}.jpg"
        final_image_path = os.path.join(CDN_SALES_IMGS, mock_filename)
        base_img.save(final_image_path, "JPEG", quality=85)
        
        final_image_url = f"/sales-imgs/{mock_filename}"
        status = "success"
    except Exception as e:
        logger.error(f"Failed to process image for item {item_id}: {str(e)}")
        status = "failed"
        error_message = str(e)
    
    payload = WebhookPayload(
        item_id=item_id,
        status=status,
        final_image_url=final_image_url,
        error_message=error_message
    )
    
    payload_json = payload.model_dump_json()
    
    # Generate HMAC-SHA256 signature
    signature = hmac.new(
        CALLBACK_SECRET.encode(),
        payload_json.encode(),
        hashlib.sha256
    ).hexdigest()
    
    headers = {
        "Content-Type": "application/json",
        "X-Signature-SHA256": signature
    }
    
    logger.info(f"Firing webhook for item {item_id} to {callback_url}")
    
    try:
        # Ngrok SSL sometimes causes issues locally, so we disable verify here for the callback.
        # We also use a null proxy to ensure the client doesn't try to use any system proxies
        # that might be interfering with the Docker network's outbound traffic.
        async with httpx.AsyncClient(verify=False, proxy=None) as client:
            response = await client.post(callback_url, content=payload_json, headers=headers)
            response.raise_for_status()
            logger.info(f"Successfully delivered webhook for item {item_id}")
    except Exception as e:
        logger.error(f"Failed to deliver webhook for item {item_id}: {str(e)}")

async def process_sales_photo_batch(request: SalesPhotoBatchRequest):
    """
    Processes each item in the batch asynchronously.
    """
    logger.info(f"Processing batch {request.batch_id} for company {request.company_id}")
    
    tasks = [
        process_sales_photo_item(item, request.callback_url)
        for item in request.items
    ]
    
    await asyncio.gather(*tasks)

from pydantic import BaseModel
from typing import List, Dict, Any

class SalesPhotoItem(BaseModel):
    item_id: int
    plant_id: int
    configuration: Dict[str, Any]

class SalesPhotoBatchRequest(BaseModel):
    batch_id: int
    company_id: int
    callback_url: str
    items: List[SalesPhotoItem]

class WebhookPayload(BaseModel):
    item_id: int
    status: str
    final_image_url: str
    error_message: str

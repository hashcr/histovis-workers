from pydantic import BaseModel


class ImageProcessMessage(BaseModel):
    imageId: str
    imageUrl: str

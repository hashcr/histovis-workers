from uuid import UUID
from pydantic import BaseModel


class JobMessage(BaseModel):
    jobId: UUID
    imageUrl: str
    args: dict[str, str] = {}

    @property
    def job_id(self) -> str:
        return str(self.jobId)
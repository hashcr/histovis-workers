from uuid import UUID
from pydantic import BaseModel


class JobMessage(BaseModel):
    jobId: UUID
    imageId: str = ""
    imageUrl: str
    args: dict[str, str] = {}

    @property
    def job_id(self) -> str:
        return str(self.jobId)


class VerifyPluginMessage(BaseModel):
    pluginId: UUID
    pluginCode: str
    scriptUrl: str
    installationTopicRoute: str

    @property
    def plugin_id(self) -> str:
        return str(self.pluginId)


class InstallPluginMessage(BaseModel):
    pluginId: UUID
    pluginCode: str
    localScriptPath: str
    installationTopicRoute: str

    @property
    def plugin_id(self) -> str:
        return str(self.pluginId)
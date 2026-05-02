class HistovisError(Exception):
    """Base exception for all histovis-workers errors."""
    pass

class UnknownPluginCodeError(HistovisError):
    """Raised when a routing key has no handler."""
    def __init__(self, plugin_code: str):
        self.plugin_code = plugin_code
        super().__init__(f"No handler registered for plygincode : '{plugin_code}'")

class JobProcessingError(HistovisError):
    """Raised when a handler fails """
    def __init__(self, job_id: str, reason: str):
        self.job_id = job_id
        self.reason = reason
        super().__init__(f"Job '{job_id}' failed: {reason} ")

class ModelNotReadyError(HistovisError):
    """Raised when model is not ready yet and requested arrived."""
    pass

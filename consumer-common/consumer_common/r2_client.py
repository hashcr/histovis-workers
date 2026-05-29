import boto3
from botocore.config import Config


def upload_bytes(
    data: bytes,
    key: str,
    *,
    internal_endpoint: str,
    public_endpoint: str,
    access_key: str,
    secret_key: str,
    bucket: str,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload bytes to an R2/S3-compatible bucket and return the public URL."""
    s3 = boto3.client(
        "s3",
        endpoint_url=internal_endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    s3.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
    return f"{public_endpoint}/{key}"

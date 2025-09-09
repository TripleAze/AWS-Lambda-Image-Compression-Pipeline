import boto3
import os
import json
import tempfile
from datetime import datetime
from PIL import Image

# AWS clients
s3 = boto3.client("s3")
dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")

# Environment variables (set these in Lambda console)
OUTPUT_BUCKET = os.environ["OUTPUT_BUCKET"]
DYNAMODB_TABLE = os.environ["DYNAMODB_TABLE"]
SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]

def lambda_handler(event, context):
    try:
        # 1. Extract bucket + object key from S3 event
        source_bucket = event["Records"][0]["s3"]["bucket"]["name"]
        object_key = event["Records"][0]["s3"]["object"]["key"]

        # Temp file paths
        download_path = os.path.join(tempfile.gettempdir(), object_key)
        upload_path = os.path.join(tempfile.gettempdir(), "compressed-" + object_key)

        # 2. Download image from input bucket
        s3.download_file(source_bucket, object_key, download_path)

        # 3. Open and compress image
        with Image.open(download_path) as img:
            img.save(upload_path, optimize=True, quality=60)  # compress to 60% quality

        # 4. Upload compressed image to output bucket
        s3.upload_file(upload_path, OUTPUT_BUCKET, "compressed-" + object_key)

        # 5. Collect metadata
        metadata = {
            "ImageID": object_key,
            "OriginalBucket": source_bucket,
            "OutputBucket": OUTPUT_BUCKET,
            "CompressedFile": "compressed-" + object_key,
            "SizeKB": os.path.getsize(upload_path) // 1024,
            "Timestamp": datetime.utcnow().isoformat()
        }

        # Save metadata to DynamoDB
        table = dynamodb.Table(DYNAMODB_TABLE)
        table.put_item(Item=metadata)

        # 6. Publish notification to SNS
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject="✅ Image Processed Successfully",
            Message=json.dumps(metadata, indent=2)
        )

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Image processed successfully", "metadata": metadata})
        }

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }

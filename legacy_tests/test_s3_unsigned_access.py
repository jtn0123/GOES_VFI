#!/usr/bin/env python3
"""
Test script for unsigned S3 access to NOAA GOES buckets.

This script tests if unsigned S3 access to NOAA GOES buckets is working correctly
by attempting to list objects in the bucket and checking for common errors.

Usage:
    python test_s3_unsigned_access.py
"""

import sys
import logging
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger("s3_test")

async def test_aioboto3_unsigned():
    """Test unsigned S3 access using aioboto3."""
    try:
        import aioboto3
        from botocore import UNSIGNED
        from botocore.config import Config

        logger.info("Creating aioboto3 session with unsigned access")
        session = aioboto3.Session()
        
        # Define configuration for unsigned access
        config = Config(signature_version=UNSIGNED)
        
        # Create S3 client with unsigned access
        logger.info("Creating S3 client with unsigned access")
        async with session.client('s3', region_name='us-east-1', config=config) as s3:
            # Try listing objects in NOAA GOES buckets
            buckets = ['noaa-goes16', 'noaa-goes18']
            
            for bucket in buckets:
                try:
                    logger.info(f"Listing objects in {bucket} bucket")
                    # Use a real path in the bucket
                    today = datetime.now()
                    yesterday = today - timedelta(days=1)
                    year = yesterday.strftime('%Y')
                    day_of_year = yesterday.strftime('%j')
                    hour = yesterday.strftime('%H')
                    prefix = f"ABI-L1b-RadC/{year}/{day_of_year}/{hour}/"
                    
                    logger.info(f"Using prefix: {prefix}")
                    
                    response = await s3.list_objects_v2(
                        Bucket=bucket,
                        Prefix=prefix,
                        MaxKeys=5
                    )
                    
                    # Check if the response contains objects
                    if 'Contents' in response and response['Contents']:
                        logger.info(f"Success! Found {len(response['Contents'])} objects in {bucket}")
                        for obj in response['Contents']:
                            logger.info(f"  - {obj['Key']} ({obj['Size']} bytes)")
                    else:
                        logger.warning(f"No objects found in {bucket} with prefix {prefix}")
                
                except Exception as e:
                    logger.error(f"Error listing objects in {bucket}: {e}")
    
    except Exception as e:
        logger.error(f"Error setting up aioboto3 S3 client: {e}")
        return False
    
    return True

def test_boto3_unsigned():
    """Test unsigned S3 access using boto3."""
    try:
        import boto3
        from botocore import UNSIGNED
        from botocore.config import Config

        logger.info("Creating boto3 session")
        session = boto3.Session()
        
        # Define configuration for unsigned access
        config = Config(signature_version=UNSIGNED)
        
        # Create S3 client with unsigned access
        logger.info("Creating S3 client with unsigned access")
        s3 = session.client('s3', region_name='us-east-1', config=config)
        
        # Try listing objects in NOAA GOES buckets
        buckets = ['noaa-goes16', 'noaa-goes18']
        
        for bucket in buckets:
            try:
                logger.info(f"Listing objects in {bucket} bucket")
                # Use a real path in the bucket
                today = datetime.now()
                yesterday = today - timedelta(days=1)
                year = yesterday.strftime('%Y')
                day_of_year = yesterday.strftime('%j')
                hour = yesterday.strftime('%H')
                prefix = f"ABI-L1b-RadC/{year}/{day_of_year}/{hour}/"
                
                logger.info(f"Using prefix: {prefix}")
                
                response = s3.list_objects_v2(
                    Bucket=bucket,
                    Prefix=prefix,
                    MaxKeys=5
                )
                
                # Check if the response contains objects
                if 'Contents' in response and response['Contents']:
                    logger.info(f"Success! Found {len(response['Contents'])} objects in {bucket}")
                    for obj in response['Contents']:
                        logger.info(f"  - {obj['Key']} ({obj['Size']} bytes)")
                else:
                    logger.warning(f"No objects found in {bucket} with prefix {prefix}")
            
            except Exception as e:
                logger.error(f"Error listing objects in {bucket}: {e}")
    
    except Exception as e:
        logger.error(f"Error setting up boto3 S3 client: {e}")
        return False
    
    return True

def show_environment_info():
    """Display environment information."""
    import os
    
    logger.info("Environment Information:")
    
    # Python version
    logger.info(f"Python version: {sys.version}")
    
    # Check for AWS environment variables
    aws_env_vars = {
        "AWS_ACCESS_KEY_ID": "REDACTED" if "AWS_ACCESS_KEY_ID" in os.environ else "Not set",
        "AWS_SECRET_ACCESS_KEY": "REDACTED" if "AWS_SECRET_ACCESS_KEY" in os.environ else "Not set",
        "AWS_SESSION_TOKEN": "REDACTED" if "AWS_SESSION_TOKEN" in os.environ else "Not set",
        "AWS_PROFILE": os.environ.get("AWS_PROFILE", "Not set"),
        "AWS_DEFAULT_REGION": os.environ.get("AWS_DEFAULT_REGION", "Not set")
    }
    logger.info(f"AWS Environment Variables: {aws_env_vars}")
    
    # Check if ~/.aws/credentials exists
    aws_credentials_path = Path.home() / ".aws" / "credentials"
    logger.info(f"AWS credentials file exists: {aws_credentials_path.exists()}")
    
    # Check if ~/.aws/config exists
    aws_config_path = Path.home() / ".aws" / "config"
    logger.info(f"AWS config file exists: {aws_config_path.exists()}")
    
    # Check for boto3 and aioboto3
    try:
        import boto3
        logger.info(f"boto3 version: {boto3.__version__}")
    except ImportError:
        logger.warning("boto3 not installed")
    
    try:
        import aioboto3
        logger.info(f"aioboto3 version: {aioboto3.__version__}")
    except ImportError:
        logger.warning("aioboto3 not installed")
    
    try:
        import botocore
        logger.info(f"botocore version: {botocore.__version__}")
    except ImportError:
        logger.warning("botocore not installed")

async def main():
    """Run all tests."""
    import os
    
    print("====== S3 Unsigned Access Test ======")
    print("This script tests if unsigned S3 access to NOAA GOES buckets is working correctly.\n")
    
    try:
        # Show environment info
        show_environment_info()
        
        print("\n=== Testing boto3 unsigned access ===")
        boto3_success = test_boto3_unsigned()
        
        print("\n=== Testing aioboto3 unsigned access ===")
        aioboto3_success = await test_aioboto3_unsigned()
        
        print("\n=== Test Results ===")
        print(f"boto3 unsigned access: {'SUCCESS' if boto3_success else 'FAILED'}")
        print(f"aioboto3 unsigned access: {'SUCCESS' if aioboto3_success else 'FAILED'}")
        
        if boto3_success and aioboto3_success:
            print("\nYour system is correctly configured for unsigned S3 access to NOAA GOES buckets!")
        else:
            print("\nThere might be issues with unsigned S3 access. Check the logs above for details.")
    
    except Exception as e:
        print(f"\nError in test: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ImportError as e:
        print(f"Import error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
#!/usr/bin/env python
"""
Check AWS credentials for GOES - VFI to make sure they're properly configured.
"""

import logging
import os
import traceback
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("aws_credentials_check.log", mode="w"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("aws_credentials_check")

try:
    import aioboto3
    import boto3
    import botocore.exceptions

    logger.info("Successfully imported boto3 and aioboto3")

    # Check AWS credentials configuration
    logger.info("Checking AWS credentials configuration")

    # Print environment variables
    aws_env_vars = {
        key: value for key, value in os.environ.items() if "AWS" in key or "aws" in key
    }

    if aws_env_vars:
        logger.info(f"Found AWS environment variables: {aws_env_vars.keys()}")
    else:
        logger.info("No AWS environment variables found")

    # Check for credentials file
    home_dir = Path.home()
    aws_credentials_file = home_dir / ".aws" / "credentials"
    aws_config_file = home_dir / ".aws" / "config"

    if aws_credentials_file.exists():
        logger.info(f"AWS credentials file found: {aws_credentials_file}")

        # Print available profiles (without showing actual credentials)
        with open(aws_credentials_file, "r") as f:
            content = f.read()

        profiles = [
            line.strip().strip("[]")
            for line in content.splitlines()
            if line.strip().startswith("[") and line.strip().endswith("]")
        ]

        logger.info(f"Available profiles in credentials file: {profiles}")
    else:
        logger.warning(f"AWS credentials file not found: {aws_credentials_file}")

    if aws_config_file.exists():
        logger.info(f"AWS config file found: {aws_config_file}")

        # Print available profiles (without showing actual credentials)
        with open(aws_config_file, "r") as f:
            content = f.read()

        profiles = [
            line.strip().strip("[]").replace("profile ", "")
            for line in content.splitlines()
            if line.strip().startswith("[") and line.strip().endswith("]")
        ]

        logger.info(f"Available profiles in config file: {profiles}")
    else:
        logger.warning(f"AWS config file not found: {aws_config_file}")

    # Try to create a session and list buckets
    logger.info("Creating a boto3 session without profile (using default credentials)")
    try:
        session = boto3.Session()
        client = session.client("s3")
        buckets = client.list_buckets()

        logger.info(
            f"Successfully connected to AWS. Found {len(buckets.get('Buckets', []))} buckets"
        )
        logger.info(f"AWS Region: {session.region_name}")
    except botocore.exceptions.NoCredentialsError:
        logger.error("No AWS credentials found. You need to configure AWS credentials")
    except botocore.exceptions.ClientError as e:
        logger.error(f"AWS Client Error: {e}")
    except Exception as e:
        logger.error(f"Error connecting to AWS: {e}")
        traceback.print_exc()

    # Try to use the aioboto3 library as well (as used by the integrity check tab)
    logger.info("Testing aioboto3 session creation (used by the integrity check tab)")
    import asyncio

    async def test_aioboto3():
        try:
            # Create a session
            session = aioboto3.Session()
            logger.info("Successfully created aioboto3 session")

            # Try to create an S3 client
            async with session.client("s3") as client:
                logger.info("Successfully created S3 client with aioboto3")
                try:
                    buckets = await client.list_buckets()
                    logger.info(
                        f"Successfully listed buckets with aioboto3. Found {len(buckets.get('Buckets', []))} buckets"
                    )
                except Exception as e:
                    logger.error(f"Error listing buckets with aioboto3: {e}")
        except Exception as e:
            logger.error(f"Error creating aioboto3 session: {e}")
            traceback.print_exc()

    # Run the async test function
    asyncio.run(test_aioboto3())

    logger.info("AWS credential check complete")

except ImportError as e:
    logger.error(f"Failed to import boto3 or aioboto3: {e}")
    logger.error(
        "Make sure you have installed the required dependencies with: pip install boto3 aioboto3"
    )
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    traceback.print_exc()

print("AWS credential check complete. See aws_credentials_check.log for details.")

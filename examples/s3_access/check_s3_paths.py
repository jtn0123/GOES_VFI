#!/usr/bin/env python3
"""
Check available paths in NOAA S3 buckets.
"""
import boto3
from botocore import UNSIGNED
from botocore.config import Config

# Configure S3 client with anonymous access
s3_config = Config(
    signature_version=UNSIGNED,
    region_name="us-east-1",
    retries={"max_attempts": 3}
)

s3 = boto3.client("s3", config=s3_config)

# Check available Level-2 products
def list_products(bucket, prefix, max_keys=20):
    """List available products with the given prefix."""
    print(f"Checking available paths in {bucket} with prefix '{prefix}':")
    
    result = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=max_keys)
    
    if "Contents" in result:
        prefixes = set()
        for item in result["Contents"]:
            key = item["Key"]
            parts = key.split("/")
            if len(parts) > 0:
                prefixes.add(parts[0])
        
        print("Available prefixes:")
        for prefix in sorted(prefixes):
            print(f"  - {prefix}")
    else:
        print("No objects found with that prefix.")

# Check the most recent year/day available
def list_recent_dates(bucket, product, max_keys=200):
    """List the most recent year/day combinations available."""
    print(f"Checking recent dates for {bucket}/{product}:")
    
    result = s3.list_objects_v2(Bucket=bucket, Prefix=f"{product}/", MaxKeys=max_keys, Delimiter="/")
    
    if "CommonPrefixes" in result:
        years = [prefix["Prefix"].strip("/") for prefix in result["CommonPrefixes"]]
        years = [year for year in years if year != product]
        
        if years:
            # Get the latest year
            latest_year = sorted(years)[-1]
            print(f"Latest year: {latest_year}")
            
            # Check days in the latest year
            day_result = s3.list_objects_v2(Bucket=bucket, Prefix=f"{latest_year}/", MaxKeys=max_keys, Delimiter="/")
            
            if "CommonPrefixes" in day_result:
                days = [prefix["Prefix"].strip("/") for prefix in day_result["CommonPrefixes"]]
                days = [day.split("/")[-1] for day in days]
                days = sorted(days)
                
                if days:
                    latest_days = days[-5:]  # Show the last 5 days
                    print(f"Recent days: {', '.join(latest_days)}")
                    
                    # Check hours in the latest day
                    hour_result = s3.list_objects_v2(Bucket=bucket, Prefix=f"{latest_year}/{latest_days[-1]}/", MaxKeys=max_keys, Delimiter="/")
                    
                    if "CommonPrefixes" in hour_result:
                        hours = [prefix["Prefix"].strip("/") for prefix in hour_result["CommonPrefixes"]]
                        hours = [hour.split("/")[-1] for hour in hours]
                        hours = sorted(hours)
                        
                        if hours:
                            latest_hours = hours[-5:]  # Show the last 5 hours
                            print(f"Recent hours: {', '.join(latest_hours)}")
                            
                            # List a few full paths for reference
                            print("Example path to check:")
                            example_path = f"{latest_year}/{latest_days[-1]}/{latest_hours[-1]}/00"
                            print(f"{product}/{example_path}/")
                            return example_path
    
    print("No recent dates found.")
    return None

# Main function
def main():
    bucket = "noaa-goes18"
    
    # Check Level-2 products
    list_products(bucket, "ABI-L2-")
    print()
    
    # Check recent dates for CMIPF (Full Disk)
    print("\nFull Disk (CMIPF):")
    cmipf_path = list_recent_dates(bucket, "ABI-L2-CMIPF")
    
    # Check recent dates for CMIPC (CONUS)
    print("\nCONUS (CMIPC):")
    cmipc_path = list_recent_dates(bucket, "ABI-L2-CMIPC")
    
    # Check recent dates for CMIPM (Mesoscale)
    print("\nMesoscale (CMIPM):")
    cmipm_path = list_recent_dates(bucket, "ABI-L2-CMIPM")
    
    # Check existence of specific paths
    if cmipf_path:
        test_path = f"ABI-L2-CMIPF/{cmipf_path}"
        print(f"\nChecking files in {test_path}:")
        result = s3.list_objects_v2(Bucket=bucket, Prefix=test_path, MaxKeys=5)
        if "Contents" in result:
            for item in result.get("Contents", [])[:3]:
                print(f"  {item['Key']}")
        else:
            print("  No files found.")

if __name__ == "__main__":
    main()
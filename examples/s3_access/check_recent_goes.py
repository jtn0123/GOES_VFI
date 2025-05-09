#!/usr/bin/env python3
"""
Check for recent GOES data in NOAA S3 buckets.
"""
import boto3
from botocore import UNSIGNED
from botocore.config import Config

# Configure S3 client with anonymous access
s3_config = Config(
    signature_version=UNSIGNED,
    region_name="us-east-1"
)

s3 = boto3.client("s3", config=s3_config)

# Check recent data
def check_recent_data():
    bucket = "noaa-goes18"
    product_types = [
        "ABI-L2-CMIPF",  # Full Disk
        "ABI-L2-CMIPC",  # CONUS
        "ABI-L2-CMIPM"   # Mesoscale
    ]
    
    print("Checking for recent GOES-18 data:")
    
    for product in product_types:
        print(f"\n{product}:")
        
        # List years
        years_result = s3.list_objects_v2(Bucket=bucket, Prefix=f"{product}/", Delimiter="/")
        if "CommonPrefixes" not in years_result:
            print("  No years found")
            continue
            
        years = [p["Prefix"].split("/")[1] for p in years_result["CommonPrefixes"]]
        latest_year = max(years)
        print(f"  Latest year: {latest_year}")
        
        # List days in latest year
        days_result = s3.list_objects_v2(Bucket=bucket, 
                                        Prefix=f"{product}/{latest_year}/", 
                                        Delimiter="/")
        if "CommonPrefixes" not in days_result:
            print("  No days found")
            continue
            
        days = [p["Prefix"].split("/")[2] for p in days_result["CommonPrefixes"]]
        latest_day = max(days)
        print(f"  Latest day: {latest_day}")
        
        # List hours in latest day
        hours_result = s3.list_objects_v2(Bucket=bucket, 
                                         Prefix=f"{product}/{latest_year}/{latest_day}/", 
                                         Delimiter="/")
        if "CommonPrefixes" not in hours_result:
            print("  No hours found")
            continue
            
        hours = [p["Prefix"].split("/")[3] for p in hours_result["CommonPrefixes"]]
        latest_hour = max(hours)
        print(f"  Latest hour: {latest_hour}")
        
        # List minutes in latest hour
        minutes_result = s3.list_objects_v2(Bucket=bucket, 
                                           Prefix=f"{product}/{latest_year}/{latest_day}/{latest_hour}/", 
                                           Delimiter="/")
        if "CommonPrefixes" not in minutes_result:
            print("  No minutes found")
            continue
            
        minutes = [p["Prefix"].split("/")[4] for p in minutes_result["CommonPrefixes"]]
        latest_minutes = sorted(minutes)[-5:]  # Show last 5 minutes
        print(f"  Recent minutes: {', '.join(latest_minutes)}")
        
        # List a few actual files
        latest_minute = latest_minutes[-1]
        files_result = s3.list_objects_v2(Bucket=bucket, 
                                         Prefix=f"{product}/{latest_year}/{latest_day}/{latest_hour}/{latest_minute}/", 
                                         MaxKeys=5)
        if "Contents" not in files_result:
            print("  No files found in latest minute")
            continue
            
        print(f"  Sample files in {latest_minute}:")
        for item in files_result.get("Contents", [])[:3]:
            filename = item["Key"].split("/")[-1]
            print(f"    {filename}")
            
        print(f"  Sample path: {product}/{latest_year}/{latest_day}/{latest_hour}/{latest_minute}/")

# Main function
if __name__ == "__main__":
    check_recent_data()
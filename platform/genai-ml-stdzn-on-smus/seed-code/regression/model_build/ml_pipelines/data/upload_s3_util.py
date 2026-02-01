# Uplaod dataset from local machine to S3 bucket 
# S3 bucket S3 URI from the python parser 
import argparse
import boto3

LOCAL_PATH = "ml_pipelines/data/abalone-dataset.csv"

def main():
    parser = argparse.ArgumentParser(
        description="Upload files to S3 using given bucket name"
    )
    parser.add_argument(
        '-s', '--s3_bucket', 
        type=str, 
        required=True,
        help='S3 bucket name'
    )
    args = parser.parse_args()
    bucket = args.s3_bucket
    key = LOCAL_PATH #"data/source"
    
    print(f"Bucket: {bucket}")
    print(f"Key:    {key}")
    s3 = boto3.client('s3')
    s3.upload_file(LOCAL_PATH, bucket, key)
    print("Done!")

if __name__ == "__main__":
    main()
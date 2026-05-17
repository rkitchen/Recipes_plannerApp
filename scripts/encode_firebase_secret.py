#!/usr/bin/env python3
import json
import base64
import sys
import os

def generate_base64_secret(filepath):
    if not os.path.exists(filepath):
        print(f"Error: Could not find {filepath}")
        sys.exit(1)

    with open(filepath, 'r') as f:
        try:
            sa = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON file. {e}")
            sys.exit(1)

    # Ensure it looks like a service account
    if 'private_key' not in sa:
        print("Error: Could not find 'private_key' in the JSON file.")
        sys.exit(1)

    # Convert back to JSON string (minified)
    j = json.dumps(sa)
    
    # Encode the JSON string to Base64
    b64_str = base64.b64encode(j.encode('utf-8')).decode('utf-8')
    
    print("\n=== YOUR BASE64 STRING ===")
    print("Copy the string below and paste it into your .env or GitHub Secrets:")
    print("====================================================================\n")
    print(b64_str)
    print("\n====================================================================\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python encode_firebase_secret.py <path-to-firebase-adminsdk.json>")
        sys.exit(1)
        
    generate_base64_secret(sys.argv[1])

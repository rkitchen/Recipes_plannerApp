#!/usr/bin/env python3
import json
import base64
import os

def generate_base64_secret():
    toml_path = os.path.join(os.path.dirname(__file__), '..', '.streamlit', 'secrets.toml')
    
    if not os.path.exists(toml_path):
        print(f"Error: Could not find {toml_path}")
        return

    with open(toml_path, 'r') as f:
        lines = f.readlines()

    sa = {}
    for line in lines:
        if line.startswith('type ='):
            sa['type'] = line.split('=')[1].strip().strip('\"')
        elif line.startswith('project_id ='):
            sa['project_id'] = line.split('=')[1].strip().strip('\"')
        elif line.startswith('private_key_id ='):
            sa['private_key_id'] = line.split('=')[1].strip().strip('\"')
        elif line.startswith('private_key ='):
            # Parse the TOML string manually to ensure NO characters are dropped
            val = line.split('=', 1)[1].strip()
            
            # Remove surrounding quotes if present
            if val.startswith('\"') and val.endswith('\"'):
                val = val[1:-1]
                
            # Replace literal backslash-n with actual newline characters
            # This is critical so the PEM file keeps exactly 64 characters per line
            val = val.replace('\\n', '\n')
            sa['private_key'] = val
            
        elif line.startswith('client_email ='):
            sa['client_email'] = line.split('=')[1].strip().strip('\"')
        elif line.startswith('client_id ='):
            sa['client_id'] = line.split('=')[1].strip().strip('\"')
        elif line.startswith('auth_uri ='):
            sa['auth_uri'] = line.split('=')[1].strip().strip('\"')
        elif line.startswith('token_uri ='):
            sa['token_uri'] = line.split('=')[1].strip().strip('\"')
        elif line.startswith('auth_provider_x509_cert_url ='):
            sa['auth_provider_x509_cert_url'] = line.split('=')[1].strip().strip('\"')
        elif line.startswith('client_x509_cert_url ='):
            sa['client_x509_cert_url'] = line.split('=')[1].strip().strip('\"')
        elif line.startswith('universe_domain ='):
            sa['universe_domain'] = line.split('=')[1].strip().strip('\"')

    # Ensure we actually parsed the key
    if 'private_key' not in sa:
        print("Error: Could not find 'private_key' in secrets.toml")
        return

    # Convert the dictionary to a JSON string
    j = json.dumps(sa)
    
    # Encode the JSON string to Base64
    b64_str = base64.b64encode(j.encode()).decode('utf-8')
    
    print("\n=== YOUR GITHUB SECRET BASE64 STRING ===\n")
    print(b64_str)
    print("\n========================================\n")

if __name__ == "__main__":
    generate_base64_secret()

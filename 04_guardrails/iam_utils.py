import boto3
import json

from rich import print as rprint
from botocore.exceptions import ClientError

# Create IAM client
iam = boto3.client('iam')

def create_iam_policy(policy_name, description, policy_document):
    """
    Creates an IAM policy
    
    Args:
        policy_name (str): Name of the policy
        description (str): Description of the policy
        policy_document (dict): Policy document as a dictionary
        
    Returns:
        dict: Created policy information including ARN if successful, None if error
    """
    try:
        # Create the IAM policy
        response = iam.create_policy(
            PolicyName=policy_name,
            Description=description,
            PolicyDocument=json.dumps(policy_document)
        )
        
        rprint(f"Successfully created policy: {policy_name}")
        rprint(f"Policy ARN: {response['Policy']['Arn']}")
        return response['Policy']
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        if error_code == 'EntityAlreadyExists':
            rprint(f"Policy {policy_name} already exists")
        elif error_code == 'LimitExceeded':
            rprint("Policy limit exceeded in the account")
        elif error_code == 'MalformedPolicyDocument':
            rprint(f"Invalid policy document: {error_message}")
        else:
            rprint(f"Error creating policy: {error_code} - {error_message}")
        return None

def verify_policy(policy_arn):
    """
    Verifies a policy exists and returns its details
    """
    try:
        # Get the policy
        response = iam.get_policy(
            PolicyArn=policy_arn
        )
        
        # Get the policy version details
        version_response = iam.get_policy_version(
            PolicyArn=policy_arn,
            VersionId=response['Policy']['DefaultVersionId']
        )
        
        rprint("\nPolicy Details:")
        rprint(f"Name: {response['Policy']['PolicyName']}")
        rprint(f"ARN: {response['Policy']['Arn']}")
        rprint(f"Description: {response['Policy'].get('Description', 'N/A')}")
        rprint("\nPolicy Document:")
        rprint(json.dumps(version_response['PolicyVersion']['Document'], indent=2))
        
        return response['Policy']
        
    except ClientError as e:
        rprint(f"Error verifying policy: {str(e)}")
        return None

def delete_policy(policy_arn):
    """
    Deletes an IAM policy
    """
    try:
        # Delete all non-default versions first
        versions = iam.list_policy_versions(PolicyArn=policy_arn)['Versions']
        for version in versions:
            if not version['IsDefaultVersion']:
                iam.delete_policy_version(
                    PolicyArn=policy_arn,
                    VersionId=version['VersionId']
                )
        
        # Delete the policy
        iam.delete_policy(PolicyArn=policy_arn)
        print(f"Successfully deleted policy: {policy_arn}")
        return True
        
    except ClientError as e:
        print(f"Error deleting policy: {str(e)}")
        return False


def attach_policy_to_role(role_name, policy_arn):
    """
    Attaches an IAM policy to a role
    
    Args:
        role_name (str): Name of the IAM role
        policy_arn (str): ARN of the policy to attach
    """
    try:
        # Attach the policy to the role
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn=policy_arn
        )
        rprint(f"Successfully attached policy {policy_arn} to role {role_name}")
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        if error_code == 'NoSuchEntity':
            rprint(f"Role {role_name} or policy not found")
        elif error_code == 'LimitExceeded':
            rprint("Policy attachment limit exceeded for the role")
        elif error_code == 'InvalidInput':
            rprint(f"Invalid input: {error_message}")
        else:
            rprint(f"Error attaching policy: {error_code} - {error_message}")
        return False

def verify_policy_attachment(role_name, policy_arn):
    """
    Verifies if a policy is attached to a role
    """
    
    try:
        response = iam.list_attached_role_policies(
            RoleName=role_name
        )
        
        # Check if policy is in the list of attached policies
        for policy in response['AttachedPolicies']:
            if policy['PolicyArn'] == policy_arn:
                rprint(f"Verified: Policy {policy_arn} is attached to role {role_name}")
                return True
                
        rprint(f"Policy {policy_arn} is not attached to role {role_name}")
        return False
        
    except ClientError as e:
        rprint(f"Error verifying policy attachment: {str(e)}")
        return False

def list_attached_policies(role_name):
    """
    Lists all policies attached to a role
    """
    
    try:
        response = iam.list_attached_role_policies(
            RoleName=role_name
        )
        
        rprint(f"\nPolicies attached to role {role_name}:")
        for policy in response['AttachedPolicies']:
            rprint(f"- {policy['PolicyName']}: {policy['PolicyArn']}")
            
        return response['AttachedPolicies']
        
    except ClientError as e:
        rprint(f"Error listing policies: {str(e)}")
        return None

def detach_policy_from_role(role_name, policy_arn):
    """
    Detaches an IAM policy from a role
    
    Args:
        role_name (str): Name of the IAM role
        policy_arn (str): ARN of the policy to detach
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Create IAM client
    
    try:
        # Detach the policy from the role
        iam.detach_role_policy(
            RoleName=role_name,
            PolicyArn=policy_arn
        )
        rprint(f"Successfully detached policy {policy_arn} from role {role_name}")
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        
        if error_code == 'NoSuchEntity':
            rprint(f"Role {role_name} or policy not found")
        else:
            rprint(f"Error detaching policy: {error_code} - {error_message}")
        return False
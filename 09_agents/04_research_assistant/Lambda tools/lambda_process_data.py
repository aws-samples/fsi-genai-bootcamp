import csv
import json
import os
from decimal import Decimal
import boto3

def lambda_handler(event, context):
    print("Received event: ")
    print(event)

    agent = event["agent"]
    actionGroup = event["actionGroup"]
    function = event["function"]
    parameters = event.get("parameters", [])

    try:
        # Initialize S3 client
        s3 = boto3.client("s3")
        
        # Use the same bucket and key that were used to upload the data
        data_bucket_name = "earnings-data-csv-us-west-2-227221598642"
        data_s3_key = "data/data.csv"
        
        # Download file from S3 to /tmp directory
        local_file_path = "/tmp/data.csv"
        print(f"Downloading from s3://{data_bucket_name}/{data_s3_key} to {local_file_path}")
        s3.download_file(data_bucket_name, data_s3_key, local_file_path)
        
        # Initialize data structure to store sums by category
        summary_data = {}
        
        # Read from the downloaded file
        with open(local_file_path, "r") as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                summary = row['Summary']
                if summary not in summary_data:
                    summary_data[summary] = {
                        'Q4_2023': Decimal('0'),
                        'Q4_2024': Decimal('0'),
                        'FY_2023': Decimal('0'),
                        'FY_2024': Decimal('0')
                    }
                
                # Add values for each period
                for period in ['Q4_2023', 'Q4_2024', 'FY_2023', 'FY_2024']:
                    try:
                        summary_data[summary][period] += Decimal(row[period])
                    except (ValueError, TypeError):
                        continue

        # Get maximum widths for nice formatting
        max_summary_width = max(len(str(summary)) for summary in summary_data.keys())
        max_summary_width = max(max_summary_width, len("Summary"))  # Consider header length too
        
        # Create the table format
        header_format = f"| {{:<{max_summary_width}}} | {{:>12}} | {{:>12}} | {{:>12}} | {{:>12}} |"
        row_format = f"| {{:<{max_summary_width}}} | {{:>12.2f}} | {{:>12.2f}} | {{:>12.2f}} | {{:>12.2f}} |"
        separator_line = f"+{'-' * (max_summary_width + 2)}+{'-' * 14}+{'-' * 14}+{'-' * 14}+{'-' * 14}+"


        # Build table output
        table_lines = []
        table_lines.append(separator_line)
        table_lines.append(header_format.format("Summary", "Q4_2023", "Q4_2024", "FY_2023", "FY_2024"))
        table_lines.append(separator_line)

        # Add data rows
        for summary, values in sorted(summary_data.items()):
            q4_2023 = float(values['Q4_2023'])
            q4_2024 = float(values['Q4_2024'])
            fy_2023 = float(values['FY_2023'])
            fy_2024 = float(values['FY_2024'])
            table_lines.append(row_format.format(
                summary, q4_2023, q4_2024, fy_2023, fy_2024
            ))
        
        table_lines.append(separator_line)

        # Join all lines with newlines
        formatted_data = "\n".join(table_lines)

        # Create response structure
        response_body = {"TEXT": {"body": formatted_data}}

        # Create a dictionary containing the response details
        action_response = {
            "actionGroup": event["actionGroup"],
            "function": event["function"],
            "functionResponse": {"responseBody": response_body},
        }

        # Return the response
        return {
            "messageVersion": event["messageVersion"],
            "response": action_response,
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "messageVersion": event["messageVersion"],
            "error": str(e)
        }

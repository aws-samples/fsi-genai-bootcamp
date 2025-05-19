# Dockerfile
FROM public.ecr.aws/lambda/python:3.11

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install -r requirements.txt --target "${LAMBDA_TASK_ROOT}"

# Copy function code
COPY lambda_code ${LAMBDA_TASK_ROOT}

# Set the CMD to execute the handler
CMD [ "index.lambda_handler" ]
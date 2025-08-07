# Makefile

# Default target executed when no arguments are given to make.
.DEFAULT_GOAL := help

# Define shell for consistency
SHELL := /bin/bash

# Self-documenting section
# Use double hash (##) for comments that should appear in the help message.
# The help target uses grep and sed/awk to extract these comments.

help: ## Display this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
        awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}' | \
        sort

setup-environment: setup-python install-cdk install-docker ## Setup the development environment by running setup-python and install-cdk
	@echo "Environment setup complete."

setup-python: ## Setup the development environment
	@echo "Setting up the python environment..."
	pip install uv
	uv sync

install-cdk: ## Installs the AWS CDK
	@echo "Installing AWS CDK..."
	# Add installation commands here
	./scripts/install_cdk.sh

install-docker: ## Install Docker
	@echo "Installing Docker..."
	# Add installation commands here
	./scripts/install_docker.sh

clean: ## Remove build artifacts
	@echo "Cleaning up..."
    # Add clean commands here

test: ## Run tests
	@echo "Running tests..."
    # Add test commands here

install: ## Install the project
	@echo "Installing project..."
    # Add install commands here

.PHONY: help build clean test install
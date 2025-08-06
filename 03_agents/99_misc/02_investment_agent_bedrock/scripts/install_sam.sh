#!/bin/bash
# check if unzip is installed
if ! [ -x "$(command -v unzip)" ]; then
  echo 'Error: unzip is not installed.' >&2
  apt-get update
  apt-get install unzip
fi

wget https://github.com/aws/aws-sam-cli/releases/latest/download/aws-sam-cli-linux-x86_64.zip --no-check-certificate
unzip aws-sam-cli-linux-x86_64.zip -d sam-installation
./sam-installation/install -i /opt/conda/sam --update
alias sam='/opt/conda/sam/current/bin/sam'
rm -rf sam-installation aws-sam-cli-linux-x86_64.zip
sam --version
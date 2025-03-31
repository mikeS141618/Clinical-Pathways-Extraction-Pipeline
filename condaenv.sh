#!/bin/bash

# Define environment name
ENV_NAME="clinical_pathways"

echo "Creating conda environment for clinical pathways extraction..."

# Create conda environment
conda create -n $ENV_NAME python=3.10 -y

# Activate the environment
eval "$(conda shell.bash hook)"
conda activate $ENV_NAME

# Install required packages
echo "Installing required packages..."
conda install -c conda-forge pdf2image pillow poppler -y
pip install anthropic

echo ""
echo "Environment '$ENV_NAME' created successfully!"
echo ""
echo "To activate the environment, run:"
echo "conda activate $ENV_NAME"
echo ""
echo "Available scripts:"
echo "1. convert_pdfs.py - Convert PDFs to images"
echo "2. extract_pathways.py - Extract clinical pathway data from images"
echo ""
echo "Workflow:"
echo "1. Activate the environment: conda activate $ENV_NAME"
echo "2. Run PDF to image conversion: python convert_pdfs.py"
echo "3. Run pathway extraction: python extract_pathways.py"

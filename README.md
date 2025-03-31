# Clinical Pathways Extraction Pipeline

## Overview

This project automates the extraction and structuring of clinical pathway information from public VA Cancer Clinical Pathways PDFs. The pipeline converts PDFs to standardized images, uses Claude AI to extract and structure the clinical decision flows, and creates optimized summaries for patient matching algorithms.

## Purpose

Clinical pathways standardize evidence-based practices to ensure high-quality, cost-effective care for patients. This tool enables rapid extraction of this information for further analysis, comparison, and integration with clinical systems, with the ultimate goal of matching patients to the most appropriate clinical pathways.

## Prerequisites

- Anaconda or Miniconda installed
- Internet connection for API calls to Claude
- API key for Anthropic's Claude

## Installation

1. Clone this repository or download the scripts to your local machine

2. Run the environment setup script:
   ```bash
   chmod +x condaenv.sh
   ./condaenv.sh
   ```

3. Activate the conda environment:
   ```bash
   conda activate clinical_pathways
   ```

## Configuration

On first run, you'll be prompted to enter your Claude API key, which will be stored in a `config.ini` file for future use.

## Workflow

### 1. Download Clinical Pathway PDFs

PDFs are sourced from the VA's public clinical pathways website: https://www.cancer.va.gov/clinical-pathways.html

Place all downloaded PDFs in a folder named `pdfs` in the project directory.

### 2. Convert PDFs to Images

```bash
python convert_pdfs.py
```

This script:
- Processes each PDF in the `pdfs` folder
- Resizes each page to 1280px width
- Crops to 648px height to focus on the important content
- Saves images in a structured format: `ripimg/[pdf_name]/pg[page_number].png`

### 3. Extract Clinical Pathway Information

```bash
python extract_pathways.py
```

This script:
- Processes each PDF's images
- Skips title slides (page 1)
- Uses Claude AI to analyze each page and extract structured information
- Generates an initial summary of the clinical pathway
- Saves all extracted data as JSON files in the `extracted_pathways` folder

## Output Format

The extraction produces JSON files with the following structure:

```json
{
  "pathway_name": "cancer_type",
  "processed_at": "timestamp",
  "responses": [
    {
      "page": 2,
      "image_file": "pg2.png",
      "response": "structured clinical pathway text",
      "thinking": "Claude's analysis process"
    },
    ...,
    {
      "page": "summary",
      "response": "comprehensive pathway summary",
      "thinking": "Claude's synthesis process"
    }
  ]
}
```

### 4. Generate Complete Summaries

```bash
python complete_summary.py
```

This script:
- Takes the previously extracted page analyses from each pathway
- Processes the full content (without truncation) when possible
- Creates comprehensive summaries that include all critical pathway elements
- Logs any pathways that exceed token limits for later processing
- Saves detailed summaries to the `complete_summaries` folder

### 5. Create Matching-Optimized Summaries

```bash
python matching_summary.py
```

This script:
- Condenses each complete pathway summary into approximately 400 words
- Focuses specifically on information needed for patient matching:
  - Key diagnostic tests
  - Specific medical conditions and criteria
  - Relevant biomarkers and classifications
  - Essential treatments and medications
- Saves these optimized summaries in both JSON and plain text formats
- Creates a consolidated file with all pathway summaries
- Output is stored in the `matching_summaries` folder

### 6. HPC Integration (External)

The matching summaries are designed to be imported into an HPC environment where:
- Patient medical records are summarized
- LLaMA or other models compare patient summaries against pathway summaries
- The most appropriate clinical pathway is identified

## Output Files

### PDF Conversion
- `ripimg/[pdf_name]/pg[number].png`: Individual page images

### Initial Extraction
- `extracted_pathways/[pdf_name]_extracted.json`: Structured page-by-page analyses with initial summary

### Complete Summaries
- `complete_summaries/[pdf_name]_complete_summary.json`: Comprehensive pathway summaries

### Matching Summaries
- `matching_summaries/[pdf_name]_matching.json`: Condensed 400-word summaries in JSON format
- `matching_summaries/[pdf_name]_matching.txt`: Plain text summaries
- `matching_summaries/all_pathway_summaries.txt`: Consolidated file with all pathway summaries

## File Descriptions

- `condaenv.sh`: Creates and configures the conda environment
- `convert_pdfs.py`: Converts PDFs to properly sized images
- `extract_pathways.py`: Analyzes images and extracts structured pathway data
- `complete_summary.py`: Generates comprehensive summaries from extracted data
- `matching_summary.py`: Creates optimized summaries for patient matching
- `config.ini`: Stores API key and configuration parameters

## Troubleshooting

### PDF Conversion Issues

- Ensure you have installed poppler via conda as specified in the setup script
- Verify PDF files aren't password-protected or corrupted

### API Errors

- Verify your API key is correct
- Check your network connection
- Ensure your account has sufficient API credits

### Token Limits

- If complete_summary.py reports pathways that need truncation, you may need to:
  - Process those pathways in chunks
  - Adjust the API configuration for larger token limits
  - Simplify the system prompt to save tokens

## Limitations and Considerations

- The extraction quality depends on the clarity and structure of the source PDFs
- Large or complex PDFs may require adjustments to the image sizing parameters
- API rate limits may affect processing of large batches
- The 400-word matching summaries are optimized for LLaMA's context window limitations

## Next Steps

The extracted and condensed pathway data can be used to:

1. Match patients to appropriate clinical pathways based on their medical records
2. Create interactive visualizations of clinical decision trees
3. Compare treatment approaches across different conditions
4. Generate patient education materials
5. Support clinical decision-making in healthcare environments

## License

This project is intended for research and educational purposes. Clinical pathways should always be verified by qualified medical professionals before clinical application.
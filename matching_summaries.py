import os
import json
import anthropic
import configparser
import re
import datetime
from pathlib import Path

# Configuration handling
CONFIG_FILE = "config.ini"
COMPLETE_SUMMARIES_DIR = "complete_summaries"
CONDENSED_SUMMARIES_DIR = "matching_summaries"
os.makedirs(CONDENSED_SUMMARIES_DIR, exist_ok=True)


def load_config():
    """Load configuration from config.ini file"""
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    else:
        raise FileNotFoundError(f"{CONFIG_FILE} not found. Please run extract_pathways.py first.")
    return config


def clean_pathway_name(filename):
    """Extract clean pathway name without version info"""
    # Remove _complete_summary.json suffix
    base_name = filename.replace("_complete_summary.json", "")

    # Remove version patterns like v1, v2, V1.2, etc.
    clean_name = re.sub(r'-v\d+(\.\d+)?(-\d+)?(-508h)?', '', base_name)

    return clean_name


def generate_condensed_summary(json_file, client, config, system_prompt):
    """Generate a condensed 400-word summary focused on patient matching"""
    print(f"\nProcessing {os.path.basename(json_file)}...")

    # Load the JSON data
    with open(json_file, 'r') as f:
        data = json.load(f)

    pathway_name = data['pathway_name']
    clean_name = clean_pathway_name(os.path.basename(json_file))

    # Extract the complete summary content
    complete_summary = data['complete_summary']['response']

    # Construct the request for condensed summary
    context_text = (
        f"I need a condensed summary of the following clinical pathway: {clean_name}\n\n"
        f"Complete pathway information:\n{complete_summary}\n\n"
    )

    summary_request = (
        "Create a condensed 400-word summary of this clinical pathway that focuses ONLY on "
        "information useful for matching patients to this pathway. Specifically highlight:\n"
        "1. Key diagnostic tests required to determine eligibility\n"
        "2. Specific medical conditions and diagnostic criteria\n"
        "3. Relevant biomarkers, staging, or classification systems\n"
        "4. Essential treatments and medications mentioned\n\n"
        "The summary should allow a model to easily identify if a patient's medical record "
        "indicates they should follow this particular clinical pathway. Format the output "
        "as a single paragraph without headings or bullet points."
    )

    full_prompt = context_text + summary_request

    # Create the message for API
    messages = [{
        "role": "user",
        "content": [{"type": "text", "text": full_prompt}]
    }]

    # Generate condensed summary
    try:
        print(f"Generating matching summary for {clean_name}...")

        # Prepare API call parameters
        api_params = {
            "model": config["API"]["model"],
            "temperature": 0.3,
            "max_tokens": 2000,
            "messages": messages,
            "system": system_prompt
        }

        response = client.messages.create(**api_params)
        condensed_summary = response.content[0].text

        # Create the output data structure
        output_data = {
            "pathway_name": clean_name,
            "original_file": os.path.basename(json_file),
            "processed_at": datetime.datetime.now().isoformat(),
            "matching_summary": condensed_summary,
            # Count words for verification
            "word_count": len(condensed_summary.split())
        }

        # Save to file
        output_file = os.path.join(CONDENSED_SUMMARIES_DIR, f"{clean_name}_matching.json")
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)

        # Also save as plain text for easier use in matching systems
        text_file = os.path.join(CONDENSED_SUMMARIES_DIR, f"{clean_name}_matching.txt")
        with open(text_file, 'w') as f:
            f.write(f"PATHWAY: {clean_name}\n\n")
            f.write(condensed_summary)

        print(f"✅ Created {output_data['word_count']}-word summary for {clean_name}")
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    # Load configuration
    config = load_config()

    # Initialize API client
    client = anthropic.Anthropic(api_key=config["API"]["key"])

    # Use specialized system prompt for this task
    system_prompt = (
        "You are a clinical pathway specialist creating concise summaries for patient matching. "
        "Your task is to identify and extract ONLY the key diagnostic elements, conditions, "
        "biomarkers, and treatments that would help determine if a patient should follow "
        "this specific pathway. Focus on concrete, specific details that would appear in "
        "patient records. Prioritize clarity and relevance for matching algorithms. "
        "Be precise about diagnostic criteria, disease classifications, and treatment "
        "indicators. Avoid general descriptions of the condition when possible."
    )

    # Find all JSON files in the complete_summaries directory
    json_files = [os.path.join(COMPLETE_SUMMARIES_DIR, f) for f in os.listdir(COMPLETE_SUMMARIES_DIR)
                  if f.endswith("_complete_summary.json") and os.path.isfile(os.path.join(COMPLETE_SUMMARIES_DIR, f))]

    if not json_files:
        print(f"No complete summary files found in {COMPLETE_SUMMARIES_DIR}")
        return

    print(f"Found {len(json_files)} summary files to process")

    # Process each JSON file
    successful = 0
    failed = 0

    for json_file in json_files:
        result = generate_condensed_summary(json_file, client, config, system_prompt)
        if result:
            successful += 1
        else:
            failed += 1

    print(f"\n===== Processing Complete =====")
    print(f"Successfully processed: {successful}")
    print(f"Failed: {failed}")

    if successful > 0:
        print(f"\nAll matching summaries have been saved to {CONDENSED_SUMMARIES_DIR}/")
        print("Each summary is available in both JSON and plain text format.")

        # Create a consolidated file with all summaries for easy import
        all_summaries = []
        for f in os.listdir(CONDENSED_SUMMARIES_DIR):
            if f.endswith("_matching.txt"):
                with open(os.path.join(CONDENSED_SUMMARIES_DIR, f), 'r') as file:
                    all_summaries.append(file.read())

        with open(os.path.join(CONDENSED_SUMMARIES_DIR, "all_pathway_summaries.txt"), 'w') as outfile:
            outfile.write("\n\n" + "=" * 50 + "\n\n".join(all_summaries))

        print(f"Created consolidated file with all summaries: {CONDENSED_SUMMARIES_DIR}/all_pathway_summaries.txt")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting application...")
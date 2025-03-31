import os
import json
import anthropic
import configparser
import datetime
from pathlib import Path

# Configuration handling
CONFIG_FILE = "config.ini"
EXTRACTED_DIR = "extracted_pathways"
COMPLETE_SUMMARIES_DIR = "complete_summaries"
os.makedirs(COMPLETE_SUMMARIES_DIR, exist_ok=True)


def load_config():
    """Load configuration from config.ini file"""
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    else:
        raise FileNotFoundError(f"{CONFIG_FILE} not found. Please run extract_pathways.py first.")
    return config


def generate_complete_summary(json_file, client, config, system_prompt):
    """Generate a complete summary for a single pathway JSON file"""
    print(f"\nProcessing {os.path.basename(json_file)}...")

    # Load the JSON data
    with open(json_file, 'r') as f:
        data = json.load(f)

    pathway_name = data['pathway_name']
    responses = data['responses']

    # Extract all non-summary responses (full text, no truncation)
    page_responses = [r for r in responses if r['page'] != 'summary']

    # Construct the context with complete page responses
    context_text = f"I need a comprehensive summary of the clinical pathway for {pathway_name}.\n\n"
    context_text += "Here are the full analyses of each page:\n\n"

    for resp in page_responses:
        page_num = resp['page']
        response_text = resp['response']
        context_text += f"=== PAGE {page_num} ANALYSIS ===\n{response_text}\n\n"

    # Add the summary request
    summary_text = (
        "Based on all the information above, please provide a comprehensive, detailed summary "
        "of this entire clinical pathway. Include all key decision points, treatment options, "
        "diagnostic criteria, and clinical workflows. Organize the information in a clear, "
        "structured format that would be useful for clinicians. This should be a definitive "
        "reference summary of the entire pathway document."
    )

    full_prompt = context_text + summary_text

    # Create the message for API
    messages = [{
        "role": "user",
        "content": [{"type": "text", "text": full_prompt}]
    }]

    # Stream response for complete summary
    try:
        print("Generating complete summary...")

        # For collecting the complete response
        summary_thinking = ""
        summary_response = ""
        in_thinking_block = False
        in_text_block = False

        # Prepare API call parameters
        api_params = {
            "model": config["API"]["model"],
            "temperature": float(config["Parameters"]["temperature"]),
            "max_tokens": int(config["Parameters"]["max_tokens"]),
            "thinking": {
                "type": "enabled",
                "budget_tokens": int(config["Parameters"]["thinking_budget"])
            },
            "messages": messages,
            "system": system_prompt
        }

        with client.messages.stream(**api_params) as stream:
            for event in stream:
                if event.type == "content_block_start":
                    if event.content_block.type == "thinking":
                        in_thinking_block = True
                        print("🧠 Thinking:")
                    elif event.content_block.type == "text":
                        in_text_block = True
                        in_thinking_block = False
                        print("\n🔮 Claude: ", end="", flush=True)

                elif event.type == "content_block_delta":
                    if event.delta.type == "thinking_delta" and in_thinking_block:
                        summary_thinking += event.delta.thinking
                        print(event.delta.thinking, end="", flush=True)
                    elif event.delta.type == "text_delta" and in_text_block:
                        summary_response += event.delta.text
                        print(event.delta.text, end="", flush=True)

                elif event.type == "content_block_stop":
                    if in_thinking_block:
                        in_thinking_block = False
                        print("\n")  # Add spacing after thinking
                    elif in_text_block:
                        in_text_block = False
                        print()  # Add a newline after text

                elif event.type == "message_stop":
                    pass

        # Create the output data structure
        output_data = {
            "pathway_name": pathway_name,
            "original_file": os.path.basename(json_file),
            "processed_at": datetime.datetime.now().isoformat(),
            "complete_summary": {
                "response": summary_response,
                "thinking": summary_thinking
            }
        }

        # Save to file
        output_file = os.path.join(COMPLETE_SUMMARIES_DIR, f"{pathway_name}_complete_summary.json")
        with open(output_file, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"\nComplete summary saved to {output_file}")
        return True

    except anthropic.BadRequestError as e:
        if "too many tokens" in str(e).lower():
            print(f"\n⚠️ Token limit exceeded for {pathway_name}. Logging for truncation.")
            with open(os.path.join(COMPLETE_SUMMARIES_DIR, "needs_truncation.log"), "a") as log:
                log.write(f"{datetime.datetime.now().isoformat()}: {os.path.basename(json_file)}\n")
            return False
        else:
            print(f"API Error: {e}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    # Load configuration
    config = load_config()

    # Initialize API client
    client = anthropic.Anthropic(api_key=config["API"]["key"])

    # Get system prompt or use default
    print("\n===== Complete Summary Generator =====")
    print("This tool generates comprehensive summaries for all extracted clinical pathways.")
    system_prompt = input("Enter system prompt (or press Enter for default): ").strip() or (
        "You are a clinical expert synthesizing medical pathway information. "
        "Your task is to create comprehensive, authoritative summaries of clinical pathways "
        "that would serve as definitive reference documents for healthcare providers. "
        "Organize information logically, emphasize key decision points, and ensure all critical "
        "diagnostic and treatment elements are included. Be thorough, precise, and clinically relevant."
    )

    # Find all JSON files in the extracted_pathways directory
    json_files = [os.path.join(EXTRACTED_DIR, f) for f in os.listdir(EXTRACTED_DIR)
                  if f.endswith("_extracted.json") and os.path.isfile(os.path.join(EXTRACTED_DIR, f))]

    if not json_files:
        print(f"No extracted pathway files found in {EXTRACTED_DIR}")
        return

    print(f"Found {len(json_files)} pathway files to process")

    # Process each JSON file
    successful = 0
    needs_truncation = 0

    for json_file in json_files:
        result = generate_complete_summary(json_file, client, config, system_prompt)
        if result:
            successful += 1
        else:
            needs_truncation += 1

    print(f"\n===== Processing Complete =====")
    print(f"Successfully processed: {successful}")
    print(f"Needs truncation: {needs_truncation}")

    if needs_truncation > 0:
        print(f"\nSome files exceeded token limits and were logged in {COMPLETE_SUMMARIES_DIR}/needs_truncation.log")
        print("You may want to process these with truncation or in chunks.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting application...")
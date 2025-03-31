import json
import os
import anthropic
import datetime
import configparser
import base64
from pathlib import Path

# Configuration handling
CONFIG_FILE = "config.ini"
DEFAULT_MODEL = "claude-3-7-sonnet-20250219"
DEFAULT_MAX_TOKENS = 64000
DEFAULT_THINKING_BUDGET = 20000
DEFAULT_TEMPERATURE = 1.0

# Directory setup
OUTPUT_DIR = "extracted_pathways"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def load_config():
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
    else:
        # First-time setup
        config["API"] = {
            "key": input("Enter your Claude API key: "),
            "model": DEFAULT_MODEL
        }
        config["Parameters"] = {
            "temperature": str(DEFAULT_TEMPERATURE),
            "max_tokens": str(DEFAULT_MAX_TOKENS),
            "thinking_budget": str(DEFAULT_THINKING_BUDGET)
        }
        with open(CONFIG_FILE, 'w') as f:
            config.write(f)
    return config


def encode_image_to_base64(image_path):
    """Encode image to base64 for API request"""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def get_image_media_type(image_path):
    """Get media type based on file extension"""
    ext = os.path.splitext(image_path)[1].lower()
    if ext == '.png':
        return "image/png"
    elif ext in ['.jpg', '.jpeg']:
        return "image/jpeg"
    elif ext == '.gif':
        return "image/gif"
    elif ext == '.webp':
        return "image/webp"
    else:
        return "image/jpeg"  # Default


def process_pathway_folder(folder_path, client, config, system_prompt):
    """Process a single pathway folder containing page images"""
    pathway_name = os.path.basename(folder_path)
    print(f"\n===== Processing {pathway_name} =====")

    # Get all PNG images in the folder sorted by page number
    image_files = sorted([f for f in os.listdir(folder_path) if f.endswith('.png')],
                         key=lambda x: int(x.replace("pg", "").replace(".png", "")))

    if len(image_files) < 2:
        print(f"Not enough pages in {pathway_name}, skipping.")
        return

    # Skip page 1 (title slide) as requested
    image_files = image_files[1:]

    # Prepare the question to ask for each page
    question = """Given a clinical pathway document for a medical condition, convert the information into a clear, structured flowchart. Follow these steps:

1. Identify the key decision points in the clinical pathway:
   - Initial assessment criteria
   - Risk stratification methods
   - First-line treatment options
   - Second-line and subsequent treatments
   - Monitoring and follow-up protocols

2. Map the logical flow between decision points, including:
   - Conditional branches (if/then scenarios)
   - Treatment sequences
   - Assessment checkpoints
   - Progression pathways

3. Include critical clinical parameters:
   - Required testing (genetic, imaging, lab values)
   - Medication specifics and timing
   - Response evaluation criteria
   - Indications for alternative pathways

4. Preserve any special considerations:
   - Patient eligibility criteria
   - Symptom-based decision making
   - Multidisciplinary consultation requirements
   - Clinical trial options

5. For complex pathways, consider dividing the flowchart into logical sections (e.g., "Initial Assessment," "First-line Treatment," "Treatment for Progression") to maintain readability.

Produce the flowchart and include a brief legend explaining any specialized notation used. If you cannot create a sufficiently detailed visual representation, provide a text-based flowchart using indentation, bullets, and directional markers (→, ↓) to show the clinical pathway flow.

When critical details must be condensed, provide a "Clinical Notes" section following the flowchart that explains important nuances that couldn't be fully captured in the visual representation. Mark this section with [SUPPLEMENTAL DETAILS] to indicate these are elements that enhance the main flowchart.

If you believe any important clinical information might be lost or unclear in your representation, flag the specific sections with [DETAIL ALERT] and provide additional clarification."""

    # Initialize API-compatible messages list with system prompt
    api_messages = []

    # Store all responses for summary
    all_responses = []

    # Process each page image
    for i, image_file in enumerate(image_files):
        image_path = os.path.join(folder_path, image_file)
        print(f"\nProcessing page {i + 2} ({image_file})...")  # +2 because we skip page 1

        # Encode image to base64
        image_base64 = encode_image_to_base64(image_path)
        media_type = get_image_media_type(image_path)

        # Create user message with image and question
        user_message = {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_base64,
                    },
                },
                {
                    "type": "text",
                    "text": question
                }
            ],
        }

        # Reset messages for each page to avoid context limit
        current_messages = [user_message]

        # Stream response from Claude API
        try:
            print("Processing...\n")

            # For collecting the complete response
            current_thinking = ""
            current_response = ""
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
                "messages": current_messages,
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
                            current_thinking += event.delta.thinking
                            print(event.delta.thinking, end="", flush=True)
                        elif event.delta.type == "text_delta" and in_text_block:
                            current_response += event.delta.text
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

            # Store the response for summary
            all_responses.append({
                "page": i + 2,  # +2 because we skip page 1
                "image_file": image_file,
                "response": current_response,
                "thinking": current_thinking
            })

        except Exception as e:
            print(f"Error: {e}")

    # Ask for a summary of all the information
    print("\n===== Requesting Summary =====")

    # Create a summary request with all the responses so far
    summary_text = "You've analyzed multiple pages of a clinical pathway document. Please provide a comprehensive summary of all the information you've extracted so far, integrating the data from all pages into a single comprehensive paragraph (200-250 words) capturing the essential elements of the pathway, including condition identification, risk stratification, treatment sequencing, monitoring approaches, and progression management. Focus on maintaining clinical accuracy while making the information accessible. Present the information in a logical flow that follows the clinical decision-making process, highlighting key decision points and treatment options without omitting critical details necessary for patient management."

    summary_messages = [{
        "role": "user",
        "content": [{"type": "text", "text": summary_text}]
    }]

    # Stream response for summary
    try:
        print("Processing summary...\n")

        # For collecting the complete response
        summary_thinking = ""
        summary_response = ""
        in_thinking_block = False
        in_text_block = False

        # Prepare API call parameters - include concise versions of previous responses as context
        context_text = "Here's a summary of my previous analyses:\n\n"
        for resp in all_responses:
            context_text += f"Page {resp['page']} analysis: {resp['response']}...\n\n"

        summary_messages = [{
            "role": "user",
            "content": [{"type": "text", "text": context_text + summary_text}]
        }]

        api_params = {
            "model": config["API"]["model"],
            "temperature": float(config["Parameters"]["temperature"]),
            "max_tokens": int(config["Parameters"]["max_tokens"]),
            "thinking": {
                "type": "enabled",
                "budget_tokens": int(config["Parameters"]["thinking_budget"])
            },
            "messages": summary_messages,
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

        # Add the summary to all responses
        all_responses.append({
            "page": "summary",
            "response": summary_response,
            "thinking": summary_thinking
        })

    except Exception as e:
        print(f"Error: {e}")

    # Save all responses to a JSON file
    output_file = os.path.join(OUTPUT_DIR, f"{pathway_name}_extracted.json")
    with open(output_file, 'w') as f:
        json.dump({
            "pathway_name": pathway_name,
            "processed_at": datetime.datetime.now().isoformat(),
            "responses": all_responses
        }, f, indent=2)

    print(f"\nPathway {pathway_name} processing complete. Results saved to {output_file}")


def main():
    # Load configuration
    config = load_config()

    # Initialize API client
    client = anthropic.Anthropic(api_key=config["API"]["key"])

    # Get system prompt
    system_prompt = input("Enter your system prompt (or press Enter for none): ").strip()
    if not system_prompt:
        system_prompt = "You are an expert in analyzing clinical pathways in medicine. Your task is to convert visual clinical pathway information into clear, structured text descriptions. Focus on accurately capturing treatment algorithms, decision points, and clinical workflows."
        print(f"Using default system prompt: {system_prompt}")

    # Get image folder path
    ripimg_folder = input(
        "Enter the path to the ripimg folder containing PDF subfolders (default is 'ripimg'): ").strip() or "ripimg"

    # Process each PDF folder
    pdf_folders = [os.path.join(ripimg_folder, f) for f in os.listdir(ripimg_folder) if
                   os.path.isdir(os.path.join(ripimg_folder, f))]

    if not pdf_folders:
        print(f"No PDF folders found in {ripimg_folder}")
        return

    print(f"Found {len(pdf_folders)} PDF folders to process")

    for folder in pdf_folders:
        process_pathway_folder(folder, client, config, system_prompt)

    print("\nAll pathways have been processed!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting application...")
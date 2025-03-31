import os
import pdf2image
from PIL import Image
from pathlib import Path


def convert_pdfs_to_images(pdf_folder="pdfs", output_folder="ripimg", target_width=1280, target_height=648):
    """
    Convert PDFs to images with a width of 1280px and cropped to a height of 648px
    to focus on the area of importance and exclude the footer.
    """

    # Create output folder if it doesn't exist
    Path(output_folder).mkdir(exist_ok=True)

    # List all PDFs in the folder
    pdf_files = [f for f in os.listdir(pdf_folder) if f.lower().endswith('.pdf')]

    print(f"Found {len(pdf_files)} PDF files to process")

    # Process each PDF
    for pdf_file in pdf_files:
        pdf_path = os.path.join(pdf_folder, pdf_file)
        pdf_name = os.path.splitext(pdf_file)[0]

        # Create folder for this PDF
        pdf_output_folder = os.path.join(output_folder, pdf_name)
        Path(pdf_output_folder).mkdir(exist_ok=True)

        print(f"Processing: {pdf_file}")

        try:
            # Convert PDF to images
            pages = pdf2image.convert_from_path(pdf_path, dpi=200)

            # Save each page as an image
            for i, page in enumerate(pages):
                # Resize the image to have a width of 1280px while maintaining aspect ratio
                width_percent = target_width / float(page.width)
                new_height = int(float(page.height) * width_percent)
                resized_img = page.resize((target_width, new_height), Image.LANCZOS)

                # Crop to keep only the top 648px (area of importance)
                # If the resized image is shorter than 648px, we keep it as is
                if new_height > target_height:
                    cropped_img = resized_img.crop((0, 0, target_width, target_height))
                else:
                    cropped_img = resized_img

                # Save the image
                output_path = os.path.join(pdf_output_folder, f"pg{i + 1}.png")
                cropped_img.save(output_path, "PNG")

            print(f"  Saved {len(pages)} pages from {pdf_file}")

        except Exception as e:
            print(f"Error processing {pdf_file}: {str(e)}")

    print("PDF to image conversion complete!")


if __name__ == "__main__":
    convert_pdfs_to_images()
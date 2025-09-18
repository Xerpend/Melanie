import os
from openai import OpenAI

def analyze_image(image_path, prompt="what's in this image?", model="gpt-5-mini"):
    """
    Analyze an image using OpenAI's vision capabilities.

    Args:
        image_path (str): Path to the image file
        prompt (str): Question about the image (default: "what's in this image?")
        model (str): OpenAI model to use (default: "gpt-5-mini")

    Returns:
        str: The model's response about the image
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Upload the image file
    with open(image_path, "rb") as file_content:
        file = client.files.create(
            file=file_content,
            purpose="vision",
        )
        file_id = file.id

    # Create the response request
    response = client.responses.create(
        model=model,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {
                    "type": "input_image",
                    "file_id": file_id,
                },
            ],
        }],
    )

    return response.output_text

def analyze_pdf(pdf_path, prompt="What is the content about?", model="gpt-5-mini"):
    """
    Analyze a PDF document using OpenAI's file processing capabilities.

    Args:
        pdf_path (str): Path to the PDF file
        prompt (str): Question about the PDF content (default: "What is the content about?")
        model (str): OpenAI model to use (default: "gpt-5-mini")

    Returns:
        str: The model's response about the PDF content
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Upload the PDF file
    with open(pdf_path, "rb") as file_content:
        file = client.files.create(
            file=file_content,
            purpose="user_data"
        )

    # Create the response request
    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "file_id": file.id,
                    },
                    {
                        "type": "input_text",
                        "text": prompt,
                    },
                ]
            }
        ]
    )

    return response.output_text

# Example usage
if __name__ == "__main__":
    # Example for image analysis
    try:
        image_result = analyze_image("path_to_your_image.jpg", "Describe this image in detail")
        print("Image Analysis:", image_result)
    except Exception as e:
        print(f"Image analysis failed: {e}")

    # Example for PDF analysis
    try:
        pdf_result = analyze_pdf("draconomicon.pdf", "What is the first dragon in the book?")
        print("PDF Analysis:", pdf_result)
    except Exception as e:
        print(f"PDF analysis failed: {e}")
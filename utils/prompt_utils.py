from typing import List, Union
import io
from PIL import Image
import tempfile
import base64
import json


def prompts_to_messages(prompts: Union[str, List[dict]]) -> List[dict]:
    """
    Converts a single prompt or a list of prompts to a list of messages.

    This function takes either a string or a list of dictionaries as input.
    If the input is a string, it converts it into a dictionary with the role as 'user' and the content as the input string.
    If the input is a list of dictionaries, it iterates over each dictionary (prompt) and converts the prompts into messages.
    Each dictionary (prompt) should have the following keys:
    - role: user or assistant
    - text_prompt: The text prompt for the role
    - image_prompt: optional image prompt for the role
    Examples:
    [{"role": "user", "text_prompt": "Hello, how are you?"}, {"role": "assistant", "text_prompt": "I am doing..."]
    [{"role": "user", "text_prompt": "Describe this image", "image_prompt": "base64 encoded image"}]

    Parameters:
    prompts (Union[str, List[dict]]): A single prompt as a string or a list of prompts as dictionaries.

    Returns:
    List[dict]: A list of messages where each message is a dictionary with 'role' and 'content'.
    """

    if type(prompts) == str:
        return [{"role": "user", "content": prompts}]

    messages = []

    for prompt in prompts:
        role = prompt["role"]
        if prompt.get("image_prompt", None):

            image = prompt["image_prompt"]
            text = prompt["text_prompt"]
            content = [
                {"type": "text", "text": text},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image,
                    },
                },
            ]
        else:
            content = [{"type": "text", "text": prompt["text_prompt"]}]

        messages.append({"role": role, "content": content})

    return messages


def convert_pdf_to_image(doc, page_number=0, dpi=150):

    page = doc.load_page(page_number)  # number of page
    pix = page.get_pixmap(dpi=150)

    temp = tempfile.NamedTemporaryFile(suffix=".png")
    pix.save(temp.name)

    img = Image.open(temp.name)

    return img


def convert_pil_image_to_b64(img):

    with io.BytesIO() as output:
        img.save(output, format="JPEG")
        b64_img = base64.b64encode(output.getvalue()).decode("utf-8")

    return b64_img


def extract_docstring_info(docstring):
    """
    Extracts the description, parameters, and their types and descriptions from a Google style docstring.

    Args:
        docstring (str): The docstring to extract information from.

    Returns:
        dict: A dictionary containing the description, parameters, and their types and descriptions.
    """
    # Find the indices of "Args:" and "Returns:"
    args_index = docstring.index("Args:")

    returns_index = docstring.index("Returns:")

    # Extract the description
    function_description = docstring[:args_index].strip()

    # Extract the parameters
    param_string = docstring[args_index + 6 : returns_index].strip()
    params = []
    for param in param_string.split("\n"):
        if param.strip() == "":
            continue
        param_name_type, description = param.strip().split(":")
        param_name, param_type = param_name_type.split("(")
        param_type = param_type[:-1]

        params.append(
            {
                "name": param_name.strip(),
                "type": param_type.strip(),
                "description": description.strip(),
            }
        )

    return {"description": function_description, "params": params}


def construct_format_parameters_prompt(parameters):
    constructed_prompt = "\n".join(
        f"<parameter>\n<name>{parameter['name']}</name>\n<type>{parameter['type']}</type>\n<description>{parameter['description']}</description>\n</parameter>"
        for parameter in parameters
    )

    return constructed_prompt


def construct_format_tool_for_claude_prompt(name, description, parameters):
    constructed_prompt = (
        "<tool_description>\n"
        f"<tool_name>{name}</tool_name>\n"
        "<description>\n"
        f"{description}\n"
        "</description>\n"
        "<parameters>\n"
        f"{construct_format_parameters_prompt(parameters)}\n"
        "</parameters>\n"
        "</tool_description>"
    )
    return constructed_prompt

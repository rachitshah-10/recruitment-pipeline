
import json
import urllib.error
import urllib.request
import re

from pydantic import BaseModel, Field, field_validator


# Input received from the React frontend
class RequirementInput(BaseModel):
    description: str = Field(min_length=10, max_length=3000)


# Structured requirements extracted by the AI model
class ExtractedRequirements(BaseModel):
    role: str = "Any"
    location: str = "Any"
    required_skills: list[str] = Field(default_factory=list)

    @field_validator("required_skills")
    @classmethod
    def clean_skills(cls, skills):
        return list(dict.fromkeys(
            skill.strip()
            for skill in skills
            if isinstance(skill, str) and skill.strip()
        ))


# NEW: Normalize role names for the existing bench matcher
def normalize_role(role: str, description: str) -> str:
    """
    Convert different representations of Forward Deployed
    Engineer into the standard role value 'FDE'.

    Also correct a missed FDE role when the original
    client description explicitly mentions it.
    """

    cleaned_role = role.strip()

    if cleaned_role.lower() in {
        "fde",
        "forward deployed engineer",
        "forward-deployed engineer"
    }:
        return "FDE"

    # If the model missed FDE, detect it in the original request
    if cleaned_role.lower() == "any":
        if re.search(
            r"\bFDEs?\b|\bforward[\s-]+deployed engineers?\b",
            description,
            flags=re.IGNORECASE
        ):
            return "FDE"

    return cleaned_role or "Any"


# Communicate with the locally running Ollama model
def extract_requirements(description: str):

    system_prompt = """
You are an AI assistant for Coforge Momentum Blue.

Your task is to extract technical staffing requirements
from natural-language client requests.

Important domain knowledge:
- FDE means Forward Deployed Engineer.
- RAG means Retrieval-Augmented Generation.
- LLM means Large Language Model.
- GenAI means Generative AI.

Role extraction rules:
- If the client mentions FDE, return "FDE".
- If the client mentions Forward Deployed Engineer,
  return "FDE".
- Do not return "Any" when FDE is explicitly mentioned.
- If no role is specified, return "Any".
- Do not invent a role that is not in the request.

Extract these fields:
1. role
2. location
3. required_skills

Rules:
- Extract only explicitly mentioned requirements.
- Do not invent technical skills.
- If role is missing, use "Any".
- If location is missing, use "Any".
- If no skills are mentioned, return an empty list.
- Preserve technical skill names.
- Return valid JSON only.

Example input:
We need an FDE in USA with Python and AWS experience.

Example output:
{
  "role": "FDE",
  "location": "USA",
  "required_skills": ["Python", "AWS"]
}
"""

    # Request sent to the local Llama 3.2 model
    payload = {
        "model": "llama3.2",
        "stream": False,
        "format": ExtractedRequirements.model_json_schema(),
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": description
            }
        ],
        "options": {
            "temperature": 0
        }
    }

    request = urllib.request.Request(
        "http://localhost:11434/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json"
        },
        method="POST"
    )

    # Send the request to Ollama
    try:
        with urllib.request.urlopen(
            request,
            timeout=90
        ) as response:
            result = json.loads(response.read())

    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(
            "Cannot connect to Ollama or the model timed out. "
            "Make sure Ollama is running."
        ) from exc

    # Validate the AI-generated response
    try:
        content = result["message"]["content"]
        parsed = json.loads(content)

        extracted = ExtractedRequirements.model_validate(
            parsed
        )

    except (KeyError, ValueError, TypeError) as exc:
        raise RuntimeError(
            "The AI model returned invalid structured requirements."
        ) from exc

    # NEW: Normalize the extracted role
    normalized_role = normalize_role(
        extracted.role,
        description
    )

    # Return structured information to FastAPI
    return {
        "role": normalized_role,
        "location": extracted.location,
        "required_skills": extracted.required_skills,
        "model": "llama3.2",
        "source": "local_llm",
        "requires_review": True
    }

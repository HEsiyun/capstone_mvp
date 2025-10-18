# cv_tool.py - VLM Integration for Field Assessment (Claude 3 Haiku)
from __future__ import annotations
import os
import re
from typing import Any, Dict, List, Optional
import json

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("[INFO] Loaded environment variables from .env")
except ImportError:
    print("[INFO] python-dotenv not installed, using system environment variables")

try:
    from openai import OpenAI
    VLM_AVAILABLE = True
except ImportError:
    VLM_AVAILABLE = False
    print("[WARN] OpenAI library required for VLM. Install: pip install openai")

# OpenRouter Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# VLM Model Selection
VLM_MODEL = "anthropic/claude-3-haiku"  # Claude 3 Haiku - good balance of speed and quality

# Other available models (uncomment to switch):
# VLM_MODEL = "google/gemini-2.0-flash-exp"     # FREE experimental
# VLM_MODEL = "google/gemini-flash-1.5"         # Stable, cheap
# VLM_MODEL = "openai/gpt-4o-mini"              # Good balance
# VLM_MODEL = "anthropic/claude-3.5-sonnet"     # Best quality (expensive)

# OpenRouter Headers (optional but recommended for rankings)
SITE_URL = "https://parks-maintenance-system.local"  # Your site URL
SITE_NAME = "Parks Maintenance Intelligence System"  # Your app name


def assess_field_condition_vlm(
    image_uri: str,
    user_query: str = "",
    rag_context: Optional[List[Dict]] = None
) -> Dict[str, Any]:
    """
    Use VLM to assess sports field condition from image
    
    Args:
        image_uri: Image URL or base64 data URI
        user_query: User's specific question
        rag_context: Optional RAG-retrieved standards for context
    
    Returns:
        {
            "condition_score": 7.5,
            "condition_label": "Good",
            "issues": ["Patchy grass", "Worn baselines"],
            "maintenance_needed": ["Mowing", "Reseeding"],
            "priority": "medium",
            "explanation": "...",
            "confidence": 0.85
        }
    """
    if not VLM_AVAILABLE:
        return _mock_assessment()
    
    if not OPENROUTER_API_KEY:
        print("[WARN] OPENROUTER_API_KEY not set, using mock data")
        return _mock_assessment()
    
    try:
        # Build context from RAG if available
        rag_info = ""
        if rag_context:
            rag_info = "\n\nRelevant Standards:\n" + "\n".join([
                f"- {hit.get('text', '')[:150]}..." 
                for hit in rag_context[:2]
            ])
        
        # Construct prompt
        base_prompt = """Analyze this sports field image and provide a detailed assessment.

Evaluate:
1. Turf/grass condition (rate 1-10)
2. Surface uniformity and bare patches
3. Line marking visibility
4. Drainage and water pooling
5. Overall maintenance state

Provide response in this JSON format:
{
  "condition_score": 7.5,
  "condition_label": "Good/Fair/Poor",
  "issues": ["issue1", "issue2"],
  "maintenance_needed": ["action1", "action2"],
  "priority": "high/medium/low",
  "explanation": "2-3 sentence summary"
}"""

        if user_query:
            base_prompt += f"\n\nUser's specific question: {user_query}"
        
        base_prompt += rag_info
        
        # Call VLM via OpenRouter (Claude 3 Haiku)
        client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY
        )
        
        print(f"[VLM] Calling model: {VLM_MODEL}")
        
        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": SITE_URL,
                "X-Title": SITE_NAME,
            },
            model=VLM_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": base_prompt},
                    {"type": "image_url", "image_url": {"url": image_uri}}
                ]
            }],
            temperature=0.3,
            max_tokens=500
        )
        
        # Parse VLM response
        vlm_output = response.choices[0].message.content.strip()
        
        # Try to extract JSON
        try:
            # Find JSON block in response
            json_match = re.search(r'\{.*\}', vlm_output, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                result["confidence"] = 0.85
                result["raw_response"] = vlm_output
                return result
        except:
            pass
        
        # Fallback: parse as plain text
        return {
            "condition_score": 7.0,
            "condition_label": "Assessment completed",
            "issues": [],
            "maintenance_needed": [],
            "priority": "medium",
            "explanation": vlm_output,
            "confidence": 0.7,
            "raw_response": vlm_output
        }
        
    except Exception as e:
        print(f"[ERROR] VLM assessment failed: {e}")
        return _mock_assessment()


def identify_field_type_vlm(
    image_uri: str,
    reference_object: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Identify field type and estimate dimensions using VLM
    
    Args:
        image_uri: Field image
        reference_object: Optional {"type": "goal", "width_meters": 7.32}
    
    Returns:
        {
            "field_type": "soccer" | "baseball" | "softball" | "multi-purpose",
            "shape": "rectangular" | "diamond",
            "detected_features": ["goals", "penalty_box", ...],
            "estimated_dimensions": {"length": 95, "width": 60},
            "suitable_for": ["U13 Soccer", "U15 Soccer"],
            "not_suitable_for": ["U18 Soccer"],
            "explanation": "..."
        }
    """
    if not VLM_AVAILABLE or not OPENROUTER_API_KEY:
        return {"field_type": "unknown", "error": "VLM not available"}
    
    try:
        ref_info = ""
        if reference_object:
            ref_info = f"\n\nReference: The {reference_object['type']} in this image is {reference_object.get('width_meters', 'unknown')} meters wide."
        
        prompt = f"""Analyze this sports field image and identify:

1. Field Type: Soccer, Baseball, Softball, Cricket, Football, or Multi-purpose
2. Shape: Rectangular or Diamond
3. Key Features: Goals, bases, pitcher's mound, line markings, etc.
4. Approximate Dimensions: If you can see the full field, estimate length and width in meters

{ref_info}

Provide detailed analysis in JSON format:
{{
  "field_type": "soccer/baseball/softball/multi-purpose",
  "shape": "rectangular/diamond", 
  "detected_features": ["feature1", "feature2"],
  "estimated_length_m": 100,
  "estimated_width_m": 65,
  "confidence": 0.85,
  "reasoning": "explanation of how you identified this"
}}"""

        client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY
        )
        
        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": SITE_URL,
                "X-Title": SITE_NAME,
            },
            model=VLM_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_uri}}
                ]
            }],
            temperature=0.2,
            max_tokens=600
        )
        
        vlm_output = response.choices[0].message.content.strip()
        
        # Parse JSON response
        json_match = re.search(r'\{.*\}', vlm_output, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            result["raw_response"] = vlm_output
            return result
        
        return {"field_type": "unknown", "raw_response": vlm_output}
        
    except Exception as e:
        print(f"[ERROR] Field identification failed: {e}")
        return {"field_type": "unknown", "error": str(e)}


def detect_maintenance_needs_vlm(
    image_uri: str,
    field_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    Detect specific maintenance needs from field image
    
    Returns:
        {
            "needs_mowing": true,
            "needs_line_marking": true,
            "needs_reseeding": false,
            "damaged_equipment": ["south goal net torn"],
            "safety_hazards": ["standing water near corner"],
            "priority_actions": [
                {"action": "Mow field", "urgency": "high", "estimated_cost": "$200-300"},
                ...
            ]
        }
    """
    if not VLM_AVAILABLE or not OPENROUTER_API_KEY:
        return {"error": "VLM not available"}
    
    field_context = f" This is a {field_type} field." if field_type else ""
    
    prompt = f"""Analyze this sports field image for maintenance needs.{field_context}

Check for:
1. Grass height - does it need mowing?
2. Line markings - are they clear or faded?
3. Bare patches - need reseeding?
4. Equipment damage - goals, nets, fences
5. Safety hazards - holes, debris, standing water

Provide assessment in JSON:
{{
  "needs_mowing": true/false,
  "grass_height_estimate": "5-8 cm / overgrown / well-maintained",
  "needs_line_marking": true/false,
  "needs_reseeding": true/false,
  "damaged_equipment": ["item1", "item2"],
  "safety_hazards": ["hazard1"],
  "priority_actions": [
    {{"action": "Mow field", "urgency": "high", "estimated_days": 1}}
  ],
  "overall_condition": "excellent/good/fair/poor"
}}"""
    
    try:
        client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY
        )
        
        response = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": SITE_URL,
                "X-Title": SITE_NAME,
            },
            model=VLM_MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_uri}}
                ]
            }],
            temperature=0.2,
            max_tokens=600
        )
        
        vlm_output = response.choices[0].message.content.strip()
        json_match = re.search(r'\{.*\}', vlm_output, re.DOTALL)
        
        if json_match:
            return json.loads(json_match.group())
        
        return {"raw_response": vlm_output}
        
    except Exception as e:
        print(f"[ERROR] Maintenance detection failed: {e}")
        return {"error": str(e)}


def cv_assess_rag(
    image_uri: str,
    topic_hint: str = "",
    user_query: str = ""
) -> Dict[str, Any]:
    """
    Main CV assessment function - integrates VLM with RAG
    
    This replaces the mock cv_tool.py with real VLM capabilities
    
    Args:
        image_uri: Image URL or path
        topic_hint: RAG search keywords
        user_query: User's original question
    """
    # Get RAG context if available
    from rag import RAG
    rag_hits = []
    if topic_hint:
        rag_hits = RAG.retrieve(topic_hint, k=3)
    
    # Check if OpenRouter is configured
    if not OPENROUTER_API_KEY:
        print("[INFO] OPENROUTER_API_KEY not set")
        print("[INFO] To enable VLM: export OPENROUTER_API_KEY='your-key'")
        return {
            "cv": {
                "condition": "Good",
                "score": 7.0,
                "labels": ["VLM not configured - set OPENROUTER_API_KEY to enable"],
                "explanations": ["Mock assessment only"],
                "low_confidence": True
            },
            "support": rag_hits
        }
    
    # Call VLM assessment
    assessment = assess_field_condition_vlm(image_uri, user_query, rag_hits)
    
    return {
        "cv": {
            "condition": assessment.get("condition_label", "Unknown"),
            "score": assessment.get("condition_score", 0),
            "labels": assessment.get("issues", []),
            "explanations": assessment.get("maintenance_needed", []),
            "low_confidence": assessment.get("confidence", 0) < 0.6
        },
        "support": rag_hits
    }


def _mock_assessment() -> Dict[str, Any]:
    """Fallback mock assessment when VLM unavailable"""
    return {
        "condition_score": 7.0,
        "condition_label": "Unknown",
        "issues": ["VLM not configured - set OPENROUTER_API_KEY to enable real image analysis"],
        "maintenance_needed": ["Get OpenRouter API key from https://openrouter.ai/"],
        "priority": "medium",
        "explanation": "Image analysis unavailable. Configure OPENROUTER_API_KEY environment variable to enable Vision Language Model assessment.",
        "confidence": 0.0
    }


# ========== Usage Examples ==========
"""
# Example 1: Simple condition assessment
result = assess_field_condition_vlm(
    image_uri="https://example.com/field.jpg",
    user_query="Is this field ready for a game?"
)

# Example 2: Field type identification
result = identify_field_type_vlm(
    image_uri="https://example.com/field.jpg",
    reference_object={"type": "goal", "width_meters": 7.32}
)

# Example 3: Maintenance needs
result = detect_maintenance_needs_vlm(
    image_uri="https://example.com/field.jpg",
    field_type="soccer"
)
"""
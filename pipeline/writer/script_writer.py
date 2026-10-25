"""
Script Writer agent utilizing Ollama (gemma4:12b).
Generates exaggerated 'informative' brainrot scripts, image queries, and YouTube metadata.
"""

import json
from typing import List
from pydantic import BaseModel, Field
import ollama

from pipeline.config import OLLAMA_HOST, DEFAULT_MODEL
from pipeline.researcher.base import ResearchResult

class ScriptBeat(BaseModel):
    text: str = Field(description="The spoken narration for this beat")
    caption_lines: List[str] = Field(
        default_factory=list,
        description="List of caption lines for screen overlay. Each line must be a separate string, avoiding raw escaped characters"
    )
    image_search_query: str = Field(description="2-4 word concrete keyword query for finding a web image")

class ScriptResult(BaseModel):
    title: str = Field(description="Viral YouTube Shorts title")
    description: str = Field(default="", description="YouTube description including hashtags and summary")
    tags: List[str] = Field(default_factory=list, description="Array of YouTube SEO tags")
    beats: List[ScriptBeat] = Field(default_factory=list, description="Sequential video beats")
    full_script: str = ""

SYSTEM_PROMPT = """You are an elite short-form video storyteller specializing in high-energy, overstimulating 'brainrot' content that feels pseudo-informative.
Your critical mission is to craft a tight, highly cohesive NARRATIVE rather than rattling off disconnected facts.

NARRATIVE ARCHITECTURE & COHESION RULES:
1. NO RANDOM TRIVIA LISTS: Do NOT jump abruptly between facts. The video must flow like a single escalating, unhinged story with an overarching theme.
2. OVERALL TOPIC HOOK (Beat 1): The first beat MUST introduce the overall topic (e.g. October 25th) and frame an overarching narrative premise (e.g. historical hubris, cursed luck, massive cover-ups, or reckless power grabs). It then introduces Fact #1 with vivid context (the stakes, the bizarre situation).
3. DEEP CONTEXTUALIZATION: For each fact, explain what actually happened and why it was absurd or high-stakes. Don't just say "X invaded Y" or "Z was crowned"—give the specific drama and context.
4. SMOOTH COMPARATIVE TRANSITIONS: Every subsequent beat MUST begin with a direct comparison to the previous fact before presenting the new one.
   Use smooth comparative bridges such as:
   - "And if you thought [Fact 1] was reckless, that same delusion mutated centuries later when..."
   - "While [Character 1] was busy [Action 1], history decided to escalate the stakes when..."
   - "Compare that royal ego to 1929, where instead of crowns, people were risking it all for..."
   - "Just like how [Fact 2] spiraled out of control, that exact same cursed energy struck..."
5. UNIFIED ENDING TAKEAWAY (Final Beat): The final beat must synthesize the narrative thread into a definitive takeaway lesson. It MUST begin with one of:
   - "This is why you never..."
   - "This is why you always..."
   - "And that is why you should never..."
   - "And that is why you should always..."
   - "Never..."
   - "Always..."
6. PACING: 3 to 4 beats total. Relentless, dramatic, and overstimulating.
7. FORMAT: Respond ONLY with valid JSON.
"""

USER_PROMPT_TEMPLATE = """Research Topic / Date: {topic}

Researched Facts:
{facts}

Create a single cohesive, escalating narrative story based on these facts.
- Beat 1 introduces the overall topic ({topic}) and Fact #1 with full context.
- Subsequent beats MUST transition SMOOTHLY by directly comparing to the previous fact.
- Final beat MUST end with a dramatic takeaway starting with 'This is why...', 'And that is why...', 'Never...', or 'Always...'.

Output JSON format:
{{
  "title": "...",
  "description": "...",
  "tags": ["..."],
  "beats": [
    {{
      "text": "...",
      "caption_lines": ["LINE ONE", "LINE TWO"],
      "image_search_query": "2-4 word visual query"
    }}
  ]
}}
"""

class ScriptWriter:
    def __init__(self, model: str = DEFAULT_MODEL, host: str = OLLAMA_HOST):
        self.model = model
        self.client = ollama.Client(host=host)

    def write_script(self, research: ResearchResult) -> ScriptResult:
        print(f"[writer] Generating script using Ollama model '{self.model}'...", flush=True)
        
        facts_text = research.raw_summary if research.raw_summary else f"Facts about {research.topic}"
        user_message = USER_PROMPT_TEMPLATE.format(topic=research.topic, facts=facts_text)
        
        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                options={"temperature": 0.75}
            )
            raw_content = response["message"]["content"].strip()
            clean_json = raw_content
            if "```" in clean_json:
                first_brace = clean_json.find("{")
                last_brace = clean_json.rfind("}")
                if first_brace != -1 and last_brace != -1:
                    clean_json = clean_json[first_brace : last_brace + 1]
            try:
                parsed_data = json.loads(clean_json)
            except Exception:
                first_brace = raw_content.find("{")
                last_brace = raw_content.rfind("}")
                parsed_data = json.loads(raw_content[first_brace : last_brace + 1])
            
            beats: List[ScriptBeat] = []
            for b in parsed_data.get("beats", []):
                # Ensure caption_lines is a list of strings and clean any accidental \n
                raw_lines = b.get("caption_lines", [])
                clean_lines = []
                if isinstance(raw_lines, list):
                    for l in raw_lines:
                        for sub in str(l).replace("\\n", "\n").split("\n"):
                            sub_clean = sub.strip()
                            if sub_clean:
                                clean_lines.append(sub_clean)
                elif isinstance(raw_lines, str):
                    for sub in raw_lines.replace("\\n", "\n").split("\n"):
                        sub_clean = sub.strip()
                        if sub_clean:
                            clean_lines.append(sub_clean)
                
                if not clean_lines:
                    # Split beat text into 4-word chunks
                    words = b.get("text", "").split()
                    clean_lines = [" ".join(words[i:i+4]) for i in range(0, len(words), 4)]

                beats.append(ScriptBeat(
                    text=b.get("text", "").strip(),
                    caption_lines=clean_lines,
                    image_search_query=b.get("image_search_query", research.topic)
                ))
            
            full_script = " ".join([beat.text for beat in beats])
            
            return ScriptResult(
                title=parsed_data.get("title", f"INSANE Facts About {research.topic} You Won't Believe!"),
                description=parsed_data.get("description", f"Unbelievable facts about {research.topic}!\n\n#shorts #brainrot #viral #history"),
                tags=parsed_data.get("tags", ["shorts", "brainrot", "history", "crazy facts", "viral"]),
                beats=beats,
                full_script=full_script
            )

        except Exception as e:
            print(f"[writer] Ollama generation error: {e}. Generating fallback script...")
            # Deterministic fallback script
            words = [f.title for f in research.facts[:3]]
            sample_beat_1 = f"Did you know what happened on {research.topic}? Scientists and historians are completely losing their minds over this!"
            sample_beat_2 = f"And that is why you should NEVER close your eyes on {research.topic}!"
            return ScriptResult(
                title=f"The CRAZIEST Fact About {research.topic}!",
                description=f"Shocking historical facts about {research.topic} you were never taught in school!\n\n#shorts #viral #history",
                tags=["shorts", "viral", "facts", "history", "brainrot"],
                beats=[
                    ScriptBeat(
                        text=sample_beat_1,
                        caption_lines=["DID YOU KNOW", f"ON {research.topic.upper()}", "MINDS WERE LOST"],
                        image_search_query=f"{research.topic} historical event"
                    ),
                    ScriptBeat(
                        text=sample_beat_2,
                        caption_lines=["AND THAT IS WHY", "NEVER CLOSE", "YOUR EYES!"],
                        image_search_query="shocked screaming face"
                    )
                ],
                full_script=f"{sample_beat_1} {sample_beat_2}"
            )

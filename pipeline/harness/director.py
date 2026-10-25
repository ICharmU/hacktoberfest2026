"""
Lead Director Agent (gemma4:12b).
Selects the best narrative archetype from the 7 distribution archetypes,
samples consensus facts, and constructs the 3-second hook, 3-beat outline, and elongated 30-179s script.
"""

import json
from typing import List
import ollama

from pipeline.config import OLLAMA_HOST, DEFAULT_MODEL
from pipeline.observability import observe
from pipeline.writer.script_writer import ScriptBeat
from .models import ConsensusResult, IdeaHook, ThreeBeatOutline, HarnessOutput
from .archetypes import get_archetype_catalog_prompt, ARCHETYPES

DIRECTOR_SYSTEM_PROMPT = """You are an elite short-form video Showrunner and Director.
Your subagents have read source material at high temperature and surfaced the verified consensus core facts.
Some facts will be included, some will be cut. YOU are the director; the subagents were just the actors.

YOUR GOAL: Take these consensus facts and construct a viral, elongated, high-retention video (STRICTLY between 30 and 179 seconds when read aloud).

NARRATIVE FORMULA & CONSTRAINTS:
1. DURATION REQUIREMENT:
   - The script must NEVER be under 30 seconds, and strictly UNDER 180 seconds.
   - Target word count: 120 to 260 words (~40 to 80 seconds at high-speed speech).
2. PACING & FLUFF:
   - Do NOT just rattle from fact to fact.
   - Always add dramatic commentary, comedic disbelief, rhetorical questions, and pacing fluff in between facts to build tension and elongate the video length.
3. ARCHETYPE SELECTION:
   - Select the single best-fitting format from the 7 Narrative Archetypes to recontextualize the mundane facts.
4. 3-SECOND HOOK:
   - Create an irresistible 3-second opening hook line and a concrete visual anchor query.
5. 3-BEAT OUTLINE (Hook -> Tension -> Resolution):
   - Beat 1 (Hook & Setup): The 3-second hook, topic introduction, and initial contextualized fact.
   - Beat 2 (Tension & Comparative Escalation): Escalating the stakes with comedic/dramatic commentary, smoothly comparing to the next consensus fact.
   - Beat 3 (Resolution & Takeaway): Final revelation leading directly into the mandatory ending takeaway.
6. MANDATORY ENDING TAKEAWAY:
   - The video MUST conclude with an unhinged, memorable takeaway or rule of thumb starting with:
     * "This is why you never..."
     * "This is why you always..."
     * "And that is why you should never..."
     * "And that is why you should always..."
     * "Never..."
     * "Always..."
7. IMAGE SPECIFICITY & GROUNDING (STRICT REQUIREMENT):
   - Every beat's `image_search_query` MUST be a concrete, ultra-specific search query naming the EXACT primary tangible entity, named historical figure, specific artifact, document, machine, building, or real-world location explicitly mentioned in that beat's spoken words.
   - FORBIDDEN SLOP: NEVER use abstract emotional or generic words such as 'chaos', 'mystery', 'shock', 'wild', 'reaction', 'dramatic', 'explosion', 'screaming', 'secret', 'insane', 'thinking'.
   - For historical figures or events, include specific qualifiers like 'portrait', 'photo', 'archive', 'painting', or the exact year/location (e.g., 'King George II portrait' instead of 'king shock', 'Charge of the Light Brigade 1854' instead of 'battle chaos').
   - For takeaway/resolution beats, anchor the query to the primary historical subject/artifact of the story, NOT a generic meme or reaction face.
   - The viewer must immediately recognize the exact entity being talked about without needing to guess or make mental leaps.
8. FORMAT: Respond ONLY with valid JSON.
"""

DIRECTOR_USER_TEMPLATE = """Topic: {topic}
Source Title: {title}

Consensus Facts (Surfaced independently across workers):
{consensus_facts}

Discarded Temperature Noise (Do not use unless needed for context):
{outliers}

{archetypes_prompt}

Direct the script. Select the best archetype, construct the 3s hook, 3-beat outline, and elongated script with commentary/fluff.
CRITICAL: Every `image_search_query` MUST be an ultra-specific, concrete name of the exact physical person, object, document, or place spoken in that beat. Absolutely NO abstract slop words ('shock', 'chaos', 'mystery', 'wild').

Output JSON format:
{{
  "selected_archetype": "id_of_archetype",
  "archetype_justification": "Why this archetype fits best",
  "hook": {{
    "verbal_hook": "3-second opening line",
    "visual_anchor_query": "Concrete 2-4 word query of the primary person, object, or event"
  }},
  "outline": {{
    "beat_1_hook": "...",
    "beat_2_tension": "...",
    "beat_3_resolution": "..."
  }},
  "beats": [
    {{
      "text": "High energy narration line with commentary...",
      "caption_lines": ["LINE ONE", "LINE TWO"],
      "image_search_query": "Concrete specific entity/person/object query directly mentioned in this beat"
    }}
  ],
  "title": "Viral YouTube Shorts Title",
  "description": "Engaging description with #shorts hashtags",
  "tags": ["shorts", "brainrot", "viral"]
}}
"""

class LeadDirectorAgent:
    def __init__(self, model: str = DEFAULT_MODEL, host: str = OLLAMA_HOST):
        self.model = model
        self.client = ollama.Client(host=host)

    @observe(name="lead_director_agent", as_type="generation")
    def direct(self, consensus: ConsensusResult) -> HarnessOutput:
        print(f"[director] Director Agent ({self.model}) selecting archetype and directing script...", flush=True)

        consensus_text = "\n".join([f"- [{cf.frequency*100:.0f}% consensus] {cf.statement}" for cf in consensus.consensus_facts])
        outliers_text = "\n".join([f"- {o}" for o in consensus.discarded_outliers[:4]]) if consensus.discarded_outliers else "(None)"
        archetypes_catalog = get_archetype_catalog_prompt()

        user_prompt = DIRECTOR_USER_TEMPLATE.format(
            topic=consensus.topic,
            title=consensus.source_title,
            consensus_facts=consensus_text,
            outliers=outliers_text,
            archetypes_prompt=archetypes_catalog
        )

        try:
            response = self.client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": DIRECTOR_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                options={"temperature": 0.75}
            )
            raw = response["message"]["content"].strip()

            import re
            first_b = raw.find("{")
            last_b = raw.rfind("}")
            if first_b != -1 and last_b != -1 and last_b > first_b:
                json_str = raw[first_b : last_b + 1]
                json_str = re.sub(r',\s*([\]}])', r'\1', json_str)
                parsed = json.loads(json_str)
            else:
                raise ValueError(f"No valid JSON object found in director response: {raw[:100]}")

            # Parse beats
            raw_beats = parsed.get("beats", [])
            beats: List[ScriptBeat] = []
            for b in raw_beats:
                raw_lines = b.get("caption_lines", [])
                clean_lines = []
                if isinstance(raw_lines, list):
                    for l in raw_lines:
                        clean_lines.append(str(l).replace("\\n", " ").strip())
                if not clean_lines:
                    words = b.get("text", "").split()
                    clean_lines = [" ".join(words[i:i+3]) for i in range(0, len(words), 3)]

                beats.append(ScriptBeat(
                    text=b.get("text", "").strip(),
                    caption_lines=clean_lines,
                    image_search_query=b.get("image_search_query", consensus.topic)
                ))

            full_script = " ".join([b.text for b in beats])
            hook_data = parsed.get("hook", {})
            hook = IdeaHook(
                verbal_hook=hook_data.get("verbal_hook", beats[0].text[:60] if beats else consensus.topic),
                visual_anchor_query=hook_data.get("visual_anchor_query", consensus.topic)
            )

            outline_data = parsed.get("outline", {})
            outline = ThreeBeatOutline(
                beat_1_hook=outline_data.get("beat_1_hook", "Hook"),
                beat_2_tension=outline_data.get("beat_2_tension", "Tension"),
                beat_3_resolution=outline_data.get("beat_3_resolution", "Resolution")
            )

            output = HarnessOutput(
                topic=consensus.topic,
                selected_archetype=parsed.get("selected_archetype", "counter_intuitive_inversion"),
                archetype_justification=parsed.get("archetype_justification", "Best fit for high-contrast tension."),
                hook=hook,
                outline=outline,
                consensus_facts=[cf.statement for cf in consensus.consensus_facts],
                beats=beats,
                full_script=full_script,
                title=parsed.get("title", f"The INSANE Truth About {consensus.topic}!"),
                description=parsed.get("description", f"Unbelievable facts about {consensus.topic}!\n\n#shorts #history #viral"),
                tags=parsed.get("tags", ["shorts", "history", "facts", "brainrot"]),
                metadata={
                    "total_workers": consensus.total_workers,
                    "consensus_facts_count": len(consensus.consensus_facts),
                    "outliers_discarded_count": len(consensus.discarded_outliers),
                    "word_count": len(full_script.split())
                }
            )

            print(f"[director] Selected Archetype: '{output.selected_archetype}'", flush=True)
            print(f"[director] 3-Second Hook: \"{output.hook.verbal_hook}\"", flush=True)
            print(f"[director] Generated {len(output.beats)} elongated beats ({len(full_script.split())} words).", flush=True)
            return output

        except Exception as e:
            print(f"[director] Error in director agent: {e}. Generating structured fallback...", flush=True)
            return self._generate_fallback(consensus)

    def _generate_fallback(self, consensus: ConsensusResult) -> HarnessOutput:
        facts = [cf.statement for cf in consensus.consensus_facts]
        f1 = facts[0] if len(facts) > 0 else f"Something completely chaotic happened with {consensus.topic}."
        f2 = facts[1] if len(facts) > 1 else "The actual events spiraled even further beyond belief."
        f3 = facts[2] if len(facts) > 2 else "It ended in pure unadulterated madness."

        b1_text = f"Stop scrolling right now, because what you think you know about {consensus.topic} is literally backwards."
        b2_text = f"Here is the insane part: {f1} You cannot make this up—people were completely blindsided by how absurd this got."
        b3_text = f"And if you thought that was unbelievable, it gets ten times worse. {f2} Nobody could have predicted how fast things would escalate."
        b4_text = f"To make matters completely unhinged: {f3} It was not just an ordinary competition—it was pure psychological warfare."
        b5_text = f"And that is why you should always double check the facts before assuming anything about {consensus.topic}!"

        # Concrete queries grounded in topic and facts
        q1 = f"{consensus.topic} archival photo"
        q2 = f"{consensus.topic} historical document"
        q3 = f"{consensus.topic} historical event"
        q4 = f"{consensus.topic} archive"
        q5 = f"{consensus.topic} history"

        beats = [
            ScriptBeat(text=b1_text, caption_lines=["STOP SCROLLING", "THINK YOU KNOW", "TOTALLY BACKWARDS"], image_search_query=q1),
            ScriptBeat(text=b2_text, caption_lines=["THE INSANE PART", "BLINDSIDED", "CANNOT MAKE THIS UP"], image_search_query=q2),
            ScriptBeat(text=b3_text, caption_lines=["TEN TIMES WORSE", "NOBODY PREDICTED", "FAST ESCALATION"], image_search_query=q3),
            ScriptBeat(text=b4_text, caption_lines=["COMPLETELY UNHINGED", "NOT ORDINARY", "PSYCHOLOGICAL WARFARE"], image_search_query=q4),
            ScriptBeat(text=b5_text, caption_lines=["AND THAT IS WHY", "ALWAYS DOUBLE CHECK", "THE FACTS!"], image_search_query=q5)
        ]
        full_script = " ".join([b.text for b in beats])
        word_count = len(full_script.split())

        return HarnessOutput(
            topic=consensus.topic,
            selected_archetype="counter_intuitive_inversion",
            archetype_justification="Fallback narrative with 5 elongated beats guaranteeing duration >= 30s.",
            hook=IdeaHook(verbal_hook=b1_text, visual_anchor_query=q1),
            outline=ThreeBeatOutline(beat_1_hook=b1_text, beat_2_tension=f"{b2_text} {b3_text} {b4_text}", beat_3_resolution=b5_text),
            consensus_facts=[cf.statement for cf in consensus.consensus_facts],
            beats=beats,
            full_script=full_script,
            title=f"The UNBELIEVABLE Secret of {consensus.topic}!",
            description=f"Shocking facts about {consensus.topic}!\n\n#shorts #viral",
            tags=["shorts", "viral", "facts"],
            metadata={"word_count": word_count}
        )

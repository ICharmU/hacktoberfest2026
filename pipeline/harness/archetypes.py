"""
Higher-Order Format Distribution Archetypes for Shorts Ideation.
"""

from typing import List, Dict
from .models import Archetype

ARCHETYPES: List[Archetype] = [
    Archetype(
        id="absurd_bureaucracy",
        name="Absurd Bureaucracy / Legal Loophole",
        description="Mundane rules, regulations, or paperwork pushed to extreme, illicit, or bizarre conclusions.",
        hook_formula="This bizarre legal loophole let one person [ridiculous consequence]...",
        exemplar="A man legally registered the sun as his private property and started demanding utility rent."
    ),
    Archetype(
        id="butterfly_catastrophe",
        name="The Butterfly Catastrophe",
        description="A tiny, trivial error, typo, or minute spec causing massive systemic damage or historic pivots.",
        hook_formula="A single tiny mistake caused [massive global disaster]...",
        exemplar="A missing hyphen in NASA's code caused the Mariner 1 rocket to explode moments after launch."
    ),
    Archetype(
        id="illusion_of_simplicity",
        name="The Illusion of Simplicity",
        description="Deceptively mundane objects or tools concealing absurd financial cost, insane engineering, or decades to create.",
        hook_formula="This everyday object costs [fortune/effort] and almost broke [industry]...",
        exemplar="The seemingly basic cardboard egg carton required aerospace patents and millions in hydraulic design."
    ),
    Archetype(
        id="spite_saga",
        name="The Spite / Petty Vengeance Saga",
        description="Massive international standards, iconic inventions, or entire companies born purely from personal pettiness or insults.",
        hook_formula="This entire multibillion-dollar empire was created purely out of petty spite...",
        exemplar="Ferruccio Lamborghini only built supercars because Enzo Ferrari told him he only knew how to drive tractors."
    ),
    Archetype(
        id="counter_intuitive_inversion",
        name="The Counter-Intuitive Inversion",
        description="The mechanical, physical, or economic reality is the exact opposite of common sense.",
        hook_formula="Everything you think you know about [topic] is literally backwards...",
        exemplar="Adding more lanes to a highway actually makes traffic slower due to Braess's paradox."
    ),
    Archetype(
        id="accidental_monopoly",
        name="The Accidental Monopoly / Secret Chokepoint",
        description="A boring, unknown company or facility silently controlling an entire critical global supply chain.",
        hook_formula="One tiny, boring company secretly controls 90% of the entire world's [product]...",
        exemplar="A single quiet factory in Japan produces the specialized resin used in every semiconductor on Earth."
    ),
    Archetype(
        id="accidental_discovery",
        name="The Accidental Discovery",
        description="A product designed for a boring, failed purpose that accidentally transformed into a massive viral hit.",
        hook_formula="This famous product was a total failure until [unintended bizarre accident]...",
        exemplar="Play-Doh was originally invented as an industrial wallpaper cleaner before toddlers started eating it."
    ),
    Archetype(
        id="community_drama",
        name="The Absurd Community / Internet Drama",
        description="A seemingly harmless subculture, forum, or hobby erupting into unhinged, high-stakes warfare.",
        hook_formula="A harmless internet community went to war over [bizarre detail]...",
        exemplar="A knitting community had a catastrophic multi-year feud over a counterfeit yarn recipe."
    )
]

def get_archetype_catalog_prompt() -> str:
    """
    Renders the archetypes into a concise formatted prompt for the Lead Director Agent.
    """
    lines = ["Available Narrative Archetypes:"]
    for idx, arc in enumerate(ARCHETYPES, 1):
        lines.append(f"{idx}. [{arc.id.upper()}] '{arc.name}': {arc.description}")
        lines.append(f"   Hook Style: {arc.hook_formula}")
    return "\n".join(lines)

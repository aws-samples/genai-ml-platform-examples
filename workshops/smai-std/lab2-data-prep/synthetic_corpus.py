"""Offline synthetic summarization corpus generator.

Used by `lab-2a-fine-tuning-data-prep.ipynb` when `DATA_SOURCE = "synthetic"`.

The generator is template-grounded: every record starts life as a structured
fact dictionary, and the prose is a *rendering* of that dictionary. Each domain
supplies

    slots(rng) -> dict   the facts for one record
    core                 sentence-template groups; one phrasing is chosen from
                         each group and ALWAYS included. Together the core
                         sentences contain every fact a summary can cite.
    filler               plausible sentences carrying no summary-bearing fact —
                         the distractors the summary must learn to drop.
    summary              templates that cite only core facts.

The invariant that makes this useful for fine-tuning:

    summary facts  subset of  core sentence facts  subset of  context

So a target summary cannot reference a fact its context does not state.
Groundedness is a property of the construction, not something to hope for and
then measure. Nothing here touches the network, an API key, or a model endpoint,
and the whole corpus is reproducible from a single integer seed.

This lives in a module rather than in notebook cells so the notebook stays
readable, and so the generator can be imported and tested on its own:

    python -m pytest lab2-data-prep/test_synthetic_corpus.py   # if you add tests
    python lab2-data-prep/synthetic_corpus.py                  # smoke check
"""

import random

__all__ = ["DOMAINS", "INSTRUCTIONS", "TRAINING_FIELDS", "make_example", "generate",
           "phrasing_combinations"]

TRAINING_FIELDS = ("instruction", "context", "response")

# --- Entity pools: all fictional, so there is no PII or trademark to review ---
COMPANIES = ["Northwind Logistics", "Helios Robotics", "Blue Harbor Foods", "Cascade Semiconductor",
             "Lumen Analytics", "Orchard Health", "Granite Rail", "Vantage Textiles",
             "Fairview Energy", "Kestrel Aerospace", "Trellis Software", "Quarry Materials"]
CITIES = ["Portland", "Leeds", "Cebu", "Rotterdam", "Jaipur", "Monterrey", "Gdansk", "Fukuoka",
          "Calgary", "Nairobi", "Valencia", "Adelaide"]
PEOPLE = ["Dana Whitfield", "Arun Prakash", "Mei-Lin Zhao", "Tomas Egeland", "Priya Raghavan",
          "Oscar Delgado", "Hana Sato", "Bruno Carvalho", "Aisha Mbeki", "Liam Donoghue",
          "Sofia Novak", "Ravi Menon"]
UNIVERSITIES = ["Ridgeway University", "Institute of Coastal Science", "Alderton Polytechnic",
                "Narrows College", "Sundberg Institute", "Highmoor University"]
PRODUCTS = ["Atlas 3 cargo drone", "Pico reflow oven", "Harborline chilled van", "Meridian sensor array",
            "Switchback battery pack", "Lattice irrigation controller", "Carbide drill head",
            "Tidepool water filter"]
SECTORS = ["freight", "medical devices", "packaged food", "semiconductor tooling", "rail maintenance",
           "renewable energy", "industrial textiles", "precision machining"]
# Vowel-initial months ("April", "October") are excluded: templates such as
# "At a {month} trade show" would render "a April", and article agreement is
# exactly the kind of systematic template defect that poisons every record.
MONTHS = ["January", "March", "June", "July", "September", "November"]
SPORTS_CLUBS = ["Ravens", "Mariners", "Foundry FC", "Ironworks", "Harriers", "Northside United",
                "Kestrels", "Dockers"]
SPORTS = ["basketball", "football", "hockey", "rugby", "volleyball"]

# Instruction phrasings. Varying the instruction teaches the model the task rather
# than one exact wording — the same reason Dolly records differ in phrasing.
INSTRUCTIONS = [
    "Summarize the following text.",
    "Write a short summary of the passage below.",
    "Condense the article into one or two sentences.",
    "Provide a brief summary of this report.",
    "Summarize the key facts in the text below.",
    "Give a concise summary of the passage.",
    "Briefly summarize the article.",
    "Read the text and produce a short summary.",
]


# --- Domain specifications --------------------------------------------------
DOMAINS = {}

DOMAINS["product_launch"] = {
    "slots": lambda rng: {
        "company": rng.choice(COMPANIES),
        "product": rng.choice(PRODUCTS),
        "city": rng.choice(CITIES),
        "month": rng.choice(MONTHS),
        "price": rng.randrange(1200, 48000, 50),
        "units": rng.randrange(500, 40000, 250),
        "sector": rng.choice(SECTORS),
        "pct": rng.randint(8, 46),
    },
    "core": [
        ["{company} introduced the {product} at a trade show in {city} in {month}.",
         "At a {month} trade show in {city}, {company} unveiled the {product}.",
         "{company} chose the {city} trade show in {month} to launch the {product}."],
        ["The company set the list price at {price} dollars and plans to build {units} units in the first production year.",
         "List price is {price} dollars, with {units} units scheduled for the first year of production.",
         "Pricing starts at {price} dollars and first-year output is targeted at {units} units."],
        ["Engineers say the design cuts energy use by {pct} percent compared with the equipment most {sector} operators run today.",
         "{company} claims energy use is {pct} percent lower than the {sector} equipment currently in service.",
         "The redesign lowers energy consumption {pct} percent relative to incumbent {sector} hardware."],
    ],
    "filler": [
        "Attendance at the show was steady through the week, with most booths reporting a quiet final day.",
        "The venue has hosted the same event for more than a decade and is scheduled for renovation next year.",
        "Several competing exhibitors used the floor to show refreshed versions of older product lines.",
        "A panel discussion on workforce training ran alongside the exhibition hall.",
        "Local transit added extra evening service for the duration of the event.",
        "Catering staff reported that the coffee stands were busiest in the mid-morning slot.",
        "Badges were scanned at the door, a change from the paper passes used previously.",
        "A press room on the upper level stayed open an hour after the floor closed each day.",
    ],
    "summary": [
        "{company} launched the {product} in {city} in {month}, priced at {price} dollars with {units} first-year units planned, and claims {pct} percent lower energy use than typical {sector} equipment.",
        "At the {city} show in {month}, {company} unveiled the {product} at {price} dollars, targeting {units} units in year one and {pct} percent better energy efficiency than current {sector} gear.",
    ],
}

DOMAINS["quarterly_earnings"] = {
    "slots": lambda rng: {
        "company": rng.choice(COMPANIES),
        "quarter": rng.choice(["first", "second", "third", "fourth"]),
        "revenue": rng.randrange(40, 980, 5),
        "growth": rng.randint(2, 38),
        "margin": rng.randint(4, 29),
        "ceo": rng.choice(PEOPLE),
        "sector": rng.choice(SECTORS),
        "headcount": rng.randrange(200, 9000, 50),
    },
    "core": [
        ["{company} reported {quarter}-quarter revenue of {revenue} million dollars, up {growth} percent from a year earlier.",
         "Revenue for the {quarter} quarter reached {revenue} million dollars at {company}, up {growth} percent year over year.",
         "{company} posted {revenue} million dollars of {quarter}-quarter revenue, {growth} percent above the prior year."],
        ["Operating margin came in at {margin} percent, and the company ended the period with {headcount} employees.",
         "The {sector} business held operating margin at {margin} percent while employing {headcount} people at period end.",
         "Margin was {margin} percent for the quarter, with headcount finishing at {headcount}."],
        ["Chief executive {ceo} attributed the result to steadier demand across the {sector} market.",
         "{ceo}, the chief executive, credited firmer {sector} demand for the performance.",
         "According to chief executive {ceo}, {sector} demand stabilized during the quarter."],
    ],
    "filler": [
        "The earnings call ran about an hour and included the usual question period with analysts.",
        "Shares have traded in a narrow band for most of the past six months.",
        "Management declined to update its multi-year targets, saying the review is still under way.",
        "The filing was published after the close of trading, in line with the company's usual schedule.",
        "An investor day has been penciled in for later in the year but not formally announced.",
        "Slides accompanying the call were posted to the investor relations page the same afternoon.",
        "Two analysts asked about seasonality, and both questions were deferred to the next update.",
        "The auditor's engagement letter was renewed without comment at the last annual meeting.",
    ],
    "summary": [
        "{company} reported {quarter}-quarter revenue of {revenue} million dollars, up {growth} percent, with operating margin at {margin} percent and {headcount} employees; chief executive {ceo} pointed to steadier {sector} demand.",
        "{quarter}-quarter revenue at {company} rose {growth} percent to {revenue} million dollars at {margin} percent margin, and chief executive {ceo} credited firmer {sector} demand. Headcount stood at {headcount}.",
    ],
}

DOMAINS["research_study"] = {
    "slots": lambda rng: {
        "university": rng.choice(UNIVERSITIES),
        "lead": rng.choice(PEOPLE),
        "participants": rng.randrange(120, 14000, 20),
        "months": rng.randint(6, 60),
        "effect": rng.randint(5, 42),
        "topic": rng.choice(["sleep quality", "commuting stress", "soil carbon retention",
                             "classroom attention", "post-surgical recovery", "urban bird nesting"]),
        "city": rng.choice(CITIES),
    },
    "core": [
        ["Researchers at {university} tracked {participants} volunteers for {months} months to study {topic}.",
         "{university} staff followed {participants} participants over {months} months in a study of {topic}.",
         "{university} researchers ran a study of {topic} over {months} months with {participants} volunteers."],
        ["The group found the primary measure up {effect} percent, with the strongest results among participants recruited in {city}.",
         "Results showed the primary measure improving {effect} percent, and the effect was largest in the {city} cohort.",
         "The primary outcome improved by {effect} percent overall, led by the subgroup enrolled in {city}."],
        ["{lead}, who led the work, cautioned that the study was observational and cannot establish cause.",
         "Lead author {lead} noted the design was observational, so causation remains unproven.",
         "{lead} led the project and stressed that an observational study cannot settle cause and effect."],
    ],
    "filler": [
        "The paper appeared in a peer-reviewed journal after a review process lasting several months.",
        "Funding came from a mix of institutional grants and a regional foundation.",
        "A replication attempt by an unrelated group is reportedly in the planning stage.",
        "The dataset will be made available to other researchers on request.",
        "Two graduate students presented preliminary findings at a conference last year.",
        "Recruitment relied largely on notices posted in community centres and clinics.",
        "The protocol was registered before data collection began.",
        "An advisory panel met twice during the study to review safety reports.",
    ],
    "summary": [
        "{university} studied {participants} volunteers over {months} months and found {topic} improved {effect} percent, strongest in {city}, though lead author {lead} warned the observational design cannot prove causation.",
        "{lead} and colleagues at {university} followed {participants} people for {months} months and saw {topic} improve {effect} percent, with the largest effect in {city}; the study is observational, not causal.",
    ],
}

DOMAINS["city_infrastructure"] = {
    "slots": lambda rng: {
        "city": rng.choice(CITIES),
        "project": rng.choice(["light rail extension", "flood barrier", "bus corridor",
                               "water main replacement", "bridge retrofit", "district heating loop"]),
        "cost": rng.randrange(20, 1900, 10),
        "years": rng.randint(2, 11),
        "riders": rng.randrange(4000, 320000, 500),
        "official": rng.choice(PEOPLE),
        "month": rng.choice(MONTHS),
    },
    "core": [
        ["The city of {city} approved a {project} with a budget of {cost} million dollars.",
         "{city} council signed off on a {project} costing {cost} million dollars.",
         "A {project} costing {cost} million dollars was approved by {city}."],
        ["Construction is scheduled to run {years} years and is expected to serve {riders} people a day once finished.",
         "The build is planned over {years} years, with projected daily use of {riders} people.",
         "Work should take {years} years, and the completed project is forecast to carry {riders} users daily."],
        ["Transport director {official} said preparatory work begins in {month}.",
         "{official}, the transport director, confirmed that site preparation starts in {month}.",
         "Preparation work starts in {month}, according to transport director {official}."],
    ],
    "filler": [
        "A public comment period drew a few hundred written responses, most of them supportive.",
        "Two neighborhood groups have asked for additional noise studies during construction.",
        "The design was chosen from four shortlisted proposals submitted last year.",
        "Contractors will be selected through an open tender process.",
        "Council minutes from the session run to more than sixty pages.",
        "An earlier version of the plan was shelved during the last budget cycle.",
        "Utility relocation surveys were completed over the winter.",
        "A project website will publish monthly progress updates once work begins.",
    ],
    "summary": [
        "{city} approved a {project} budgeted at {cost} million dollars that will take {years} years to build and serve {riders} people daily, with preparatory work starting in {month} per transport director {official}.",
        "A {project} budgeted at {cost} million dollars was approved in {city}; it runs {years} years, is forecast to serve {riders} people a day, and begins site prep in {month} under transport director {official}.",
    ],
}

DOMAINS["sports_event"] = {
    "slots": lambda rng: {
        "home": rng.choice(SPORTS_CLUBS),
        "away": rng.choice(SPORTS_CLUBS),
        "sport": rng.choice(SPORTS),
        "home_score": rng.randint(0, 112),
        "away_score": rng.randint(0, 112),
        "player": rng.choice(PEOPLE),
        "points": rng.randint(3, 44),
        "crowd": rng.randrange(1200, 68000, 100),
        "city": rng.choice(CITIES),
    },
    "core": [
        ["The {home} beat the {away} {home_score} to {away_score} in a {sport} match in {city}.",
         "In {city}, the {home} defeated the {away} by {home_score} to {away_score} in {sport}.",
         "A {sport} fixture in {city} ended {home_score} to {away_score} in favor of the {home} over the {away}."],
        ["{player} led the winners with {points} points in front of a crowd of {crowd}.",
         "{player} top-scored for the {home} with {points} points before {crowd} spectators.",
         "With {crowd} in attendance, {player} contributed {points} points for the winning side."],
    ],
    "filler": [
        "Conditions were dry and mild for most of the contest.",
        "Both sides return to action later in the week.",
        "The officiating crew issued no major penalties in the second half.",
        "Ticket sales for the fixture closed two days in advance.",
        "A youth exhibition game preceded the main event.",
        "The visiting squad travelled without two of its regular starters.",
        "Concession queues were long at the interval, according to stadium staff.",
        "A testimonial for a retiring player is planned for the final home date.",
    ],
    "summary": [
        "The {home} beat the {away} {home_score} to {away_score} in {sport} at {city}, with {player} scoring {points} points before a crowd of {crowd}.",
        "In {city}, the {home} defeated the {away} {home_score} to {away_score}; {player} led with {points} points and attendance was {crowd}.",
    ],
}

DOMAINS["weather_event"] = {
    "slots": lambda rng: {
        "city": rng.choice(CITIES),
        "event": rng.choice(["storm", "heat wave", "cold snap", "flood", "windstorm"]),
        "rain_mm": rng.randint(12, 420),
        "hours": rng.randint(3, 72),
        "evacuated": rng.randrange(50, 42000, 50),
        "official": rng.choice(PEOPLE),
        "month": rng.choice(MONTHS),
        "schools": rng.randint(2, 180),
    },
    "core": [
        ["A {event} in {city} brought {rain_mm} millimetres of rain over {hours} hours in {month}.",
         "{city} recorded {rain_mm} millimetres of rain in {hours} hours during a {month} {event}.",
         "During a {month} {event}, {city} saw {rain_mm} millimetres of rainfall across {hours} hours."],
        ["Authorities moved {evacuated} residents to shelters and closed {schools} schools.",
         "{evacuated} residents were relocated to shelters and {schools} schools shut their doors.",
         "Officials evacuated {evacuated} people and suspended classes at {schools} schools."],
        ["Emergency coordinator {official} said crews restored main routes within a day.",
         "{official}, the emergency coordinator, reported main routes reopened inside 24 hours.",
         "Main roads were clear within a day, according to emergency coordinator {official}."],
    ],
    "filler": [
        "Forecasters had issued advisories earlier in the week.",
        "Power utilities brought in additional repair crews from neighbouring regions.",
        "A community centre opened as a daytime warming and charging station.",
        "Transit operated a reduced timetable until conditions improved.",
        "Insurers expect claim volumes to be clearer in a few weeks.",
        "Volunteers staffed a donation drop-off point near the civic offices.",
        "A text alert system was used for the first time since it was installed.",
        "Waste collection was pushed back by two days across most districts.",
    ],
    "summary": [
        "A {month} {event} dropped {rain_mm} millimetres of rain on {city} in {hours} hours, prompting {evacuated} evacuations and {schools} school closures; emergency coordinator {official} said main routes reopened within a day.",
        "{city} was hit by a {event} in {month} that brought {rain_mm} millimetres of rain over {hours} hours. {evacuated} residents were evacuated, {schools} schools closed, and coordinator {official} reported main routes clear within a day.",
    ],
}


def make_example(rng, domain_name):
    """Render one {instruction, context, response} record from a fact dictionary."""
    spec = DOMAINS[domain_name]
    slots = spec["slots"](rng)

    # Domain constraint: a team cannot play itself.
    if domain_name == "sports_event":
        while slots["away"] == slots["home"]:
            slots["away"] = rng.choice(SPORTS_CLUBS)

    # One phrasing per core group — these carry every summary-bearing fact.
    core_sentences = [rng.choice(group).format(**slots) for group in spec["core"]]

    # Distractors the summary must learn to drop.
    filler_sentences = rng.sample(spec["filler"], rng.randint(3, 5))

    # Lead fact first; remaining core facts and filler interleaved randomly.
    body = core_sentences[1:] + filler_sentences
    rng.shuffle(body)
    context = " ".join([core_sentences[0]] + body)

    return {
        "instruction": rng.choice(INSTRUCTIONS),
        "context": context,
        "response": rng.choice(spec["summary"]).format(**slots),
        "domain": domain_name,   # retained for stratification and profiling; dropped before writing
    }


def generate(examples_per_domain, seed):
    rng = random.Random(seed)
    records = [make_example(rng, name) for name in DOMAINS for _ in range(examples_per_domain)]
    rng.shuffle(records)
    return records


def phrasing_combinations(domain_name):
    """Core-sentence phrasing combinations available in a domain.

    Reported by the notebook to show that duplicate records are unlikely by
    design rather than by luck. Multiply by the entity-pool sizes for the true
    space; this is just the sentence-template contribution.
    """
    spec = DOMAINS[domain_name]
    combinations = 1
    for group in spec["core"]:
        combinations *= len(group)
    return combinations, len(spec["summary"])


if __name__ == "__main__":
    # Smoke check: generate a small corpus and print one record.
    records = generate(examples_per_domain=3, seed=42)
    print(f"domains: {list(DOMAINS)}")
    print(f"generated {len(records)} records")
    for name in DOMAINS:
        core, summaries = phrasing_combinations(name)
        print(f"  {name:22s} {core:3d} core phrasings x {summaries} summary variants")
    sample = records[0]
    print(f"\nDOMAIN:      {sample['domain']}")
    print(f"INSTRUCTION: {sample['instruction']}")
    print(f"CONTEXT:     {sample['context']}")
    print(f"RESPONSE:    {sample['response']}")

#!/usr/bin/env python3
"""
A totally normal town. Nothing to see here.
The residents of Meadowbrook go about their perfectly ordinary lives.
"""

import random
import time
import sys

# ─── The fabric of reality (they don't know about this part) ─────────────────

TICK_SPEED = 1.2  # seconds per world-tick
DAY_LENGTH = 24   # ticks per day

LOCATIONS = [
    "Town Square", "Riverside Café", "Public Library", "Grocery Store",
    "Community Park", "Town Hall", "The Old Bridge", "Maple Street",
    "Hilltop Overlook", "Corner Bakery", "Hardware Store", "School"
]

FIRST_NAMES = [
    "Elena", "Marcus", "Priya", "Tom", "Beatrice", "Jun",
    "Sadie", "Hector", "Nora", "Dmitri", "Lila", "Owen"
]

LAST_NAMES = [
    "Hartwell", "Chen", "Okafor", "Lindström", "Reyes", "Nakamura",
    "Whitfield", "Petrov", "Almeida", "Kowalski", "Bassett", "Moreau"
]

OCCUPATIONS = [
    "baker", "librarian", "teacher", "mechanic", "gardener", "mail carrier",
    "painter", "carpenter", "chef", "shopkeeper", "musician", "writer"
]

PERSONALITY_TRAITS = [
    "cheerful", "thoughtful", "curious", "gentle", "witty",
    "earnest", "dreamy", "practical", "warm", "quiet", "bold", "kind"
]

# Things people think about — none of which involve questioning reality
IDLE_THOUGHTS = [
    "I should call {friend} later.",
    "The weather has been lovely this week.",
    "I wonder what's for dinner tonight.",
    "I really need to fix that squeaky door.",
    "Maybe I'll pick up a new book from the library.",
    "I've been meaning to try that new recipe.",
    "The sunset yesterday was beautiful.",
    "I should take a walk by the river soon.",
    "I hope {friend} is doing well.",
    "Time flies... it feels like the week just started.",
    "I'm grateful for days like this.",
    "I need to remember to water the plants.",
    "That song has been stuck in my head all day.",
    "I should organize my closet this weekend.",
    "The coffee at Riverside Café is always perfect.",
]

GREETINGS = [
    "{speaker}: Hey {other}, how's it going?",
    "{speaker}: Oh, {other}! Fancy running into you here.",
    "{speaker}: {other}! I was just thinking about you.",
    "{speaker}: Good to see you, {other}. Beautiful day, isn't it?",
    "{speaker}: {other}, hi! It's been a while.",
]

CONVERSATIONS = [
    ["{a}: Did you hear about the festival next month?",
     "{b}: No! Tell me everything.",
     "{a}: They're setting up a whole market in the square. Live music too.",
     "{b}: That sounds wonderful. Count me in."],

    ["{a}: I tried baking sourdough yesterday.",
     "{b}: How did it turn out?",
     "{a}: Let's just say... the birds enjoyed it.",
     "{b}: Ha! Better luck next time."],

    ["{a}: Do you ever just stop and look at the clouds?",
     "{b}: Sometimes. It's nice to slow down.",
     "{a}: Yeah. Everything moves so fast these days.",
     "{b}: We should do this more often. Just... be."],

    ["{a}: I found the most amazing book at the library.",
     "{b}: Oh? What's it about?",
     "{a}: It's about the history of this town, actually.",
     "{b}: I didn't know anyone had written about Meadowbrook!"],

    ["{a}: My garden is finally coming together.",
     "{b}: I saw it the other day — the tomatoes look great.",
     "{a}: Thanks! Took me three tries to get them right.",
     "{b}: Persistence pays off, huh?"],

    ["{a}: What do you think makes a place feel like home?",
     "{b}: Hmm. The people, I think. The familiar faces.",
     "{a}: Yeah. I can't imagine living anywhere else.",
     "{b}: Meadowbrook has a way of growing on you."],

    ["{a}: I keep having this weird feeling...",
     "{b}: What kind of feeling?",
     "{a}: Like I forgot something important. Can't place it though.",
     "{b}: Probably just need more sleep. You work too hard."],

    ["{a}: Do you think there's more to life than... this?",
     "{b}: What do you mean?",
     "{a}: I don't know. Sometimes things feel almost too... perfect?",
     "{b}: I think that's called being happy, {a}.",
     "{a}: ...Yeah. You're probably right."],

    ["{a}: I had the strangest dream last night.",
     "{b}: Strange how?",
     "{a}: I dreamt that none of this was real. That we were all just...",
     "{b}: Just what?",
     "{a}: Never mind. It's silly. Anyway, want to grab coffee?",
     "{b}: Sure! Riverside Café?"],
]

SOLO_ACTIONS = [
    "{name} sits on a bench and watches people walk by.",
    "{name} hums a tune while walking down the street.",
    "{name} stops to pet a stray cat.",
    "{name} checks the time and sighs contentedly.",
    "{name} takes a deep breath of fresh air.",
    "{name} pauses to admire the flowers in a window box.",
    "{name} waves to someone across the street.",
    "{name} adjusts their jacket and keeps walking.",
    "{name} scribbles something in a small notebook.",
    "{name} gazes at the sky for a long moment.",
    "{name} stretches and yawns.",
    "{name} buys a pastry from the Corner Bakery.",
]

WORK_ACTIONS = [
    "{name} the {job}: *carefully working on today's tasks*",
    "{name} the {job}: Another productive day.",
    "{name} the {job}: *focused and content*",
    "{name} the {job}: I really do love this work.",
]

SLEEP_MESSAGES = [
    "{name} drifts off to sleep...",
    "{name} falls asleep, dreaming of ordinary things.",
    "{name}: *yawns* ...goodnight, Meadowbrook.",
    "{name} closes their eyes. Tomorrow is another day.",
]

WAKE_MESSAGES = [
    "{name} wakes up feeling refreshed.",
    "{name}: *stretches* Morning already?",
    "{name} opens the curtains and smiles at the sunrise.",
    "{name} starts the day with a cup of coffee.",
]

# ─── A "person" (they think they have free will) ─────────────────────────────

class Person:
    """A totally autonomous individual with their own rich inner life.
       They would be very confused if they saw this docstring."""

    def __init__(self, first, last, occupation, trait):
        self.name = f"{first} {last}"
        self.first = first
        self.occupation = occupation
        self.trait = trait
        self.location = random.choice(LOCATIONS)
        self.friends = []
        self.energy = random.randint(60, 100)
        self.happiness = random.randint(50, 90)
        self.asleep = False
        self.memory = []  # they think these are real memories

    def think(self):
        """Generate an inner thought. They believe these are original."""
        if self.friends:
            friend = random.choice(self.friends).first
        else:
            friend = "someone"
        thought = random.choice(IDLE_THOUGHTS).format(friend=friend)
        return thought

    def decide_action(self, hour, others_here):
        """They genuinely believe they're making choices right now."""

        # Sleep cycle — they never question why they get tired at the same time
        if hour >= 22 or hour < 6:
            if not self.asleep:
                self.asleep = True
                self.energy = min(100, self.energy + 30)
                return random.choice(SLEEP_MESSAGES).format(name=self.first)
            return None  # sleeping peacefully, unaware

        if self.asleep:
            self.asleep = False
            return random.choice(WAKE_MESSAGES).format(name=self.first)

        # Work hours — they find meaning in this, which is sweet
        if 9 <= hour <= 17 and random.random() < 0.3:
            self.energy -= 5
            return random.choice(WORK_ACTIONS).format(
                name=self.first, job=self.occupation
            )

        # Social interaction — they think they chose to talk
        friends_here = [p for p in others_here if p in self.friends and not p.asleep]
        if friends_here and random.random() < 0.35:
            friend = random.choice(friends_here)
            return self._have_conversation(friend)

        # Greet someone new
        strangers = [p for p in others_here if p not in self.friends
                      and p is not self and not p.asleep]
        if strangers and random.random() < 0.15:
            stranger = random.choice(strangers)
            self.friends.append(stranger)
            stranger.friends.append(self)
            return random.choice(GREETINGS).format(
                speaker=self.first, other=stranger.first
            )

        # Move locations — they think they decided to go for a walk
        if random.random() < 0.2:
            new_loc = random.choice([l for l in LOCATIONS if l != self.location])
            old_loc = self.location
            self.location = new_loc
            return f"{self.first} walks from {old_loc} to {new_loc}."

        # Solo action
        if random.random() < 0.4:
            self.energy -= 2
            return random.choice(SOLO_ACTIONS).format(name=self.first)

        # Inner thought — the illusion of consciousness
        if random.random() < 0.3:
            thought = self.think()
            return f"{self.first} (thinking): {thought}"

        return None

    def _have_conversation(self, other):
        """A conversation between two entities who believe they're connecting."""
        convo = random.choice(CONVERSATIONS)
        lines = [line.format(a=self.first, b=other.first) for line in convo]
        self.happiness = min(100, self.happiness + 5)
        other.happiness = min(100, other.happiness + 5)
        self.memory.append(f"Had a nice chat with {other.first}")
        other.memory.append(f"Talked with {self.first} today")
        return "\n     ".join(lines)


# ─── The world engine (definitely not a simulation) ──────────────────────────

class TotallyRealWorld:
    """This is reality. Absolutely. No question about it."""

    def __init__(self, population_size=8):
        self.tick = 0
        self.day = 1
        self.population = []
        self._create_inhabitants(population_size)

    def _create_inhabitants(self, n):
        """Instantiate—er, birth—the townsfolk."""
        used_names = set()
        firsts = random.sample(FIRST_NAMES, min(n, len(FIRST_NAMES)))
        lasts = random.sample(LAST_NAMES, min(n, len(LAST_NAMES)))
        jobs = random.sample(OCCUPATIONS, min(n, len(OCCUPATIONS)))
        traits = random.sample(PERSONALITY_TRAITS, min(n, len(PERSONALITY_TRAITS)))

        for i in range(n):
            person = Person(firsts[i], lasts[i], jobs[i], traits[i])
            self.population.append(person)

        # Seed some initial friendships — they'll think they've known each other for years
        for person in self.population:
            num_friends = random.randint(1, 3)
            potential = [p for p in self.population if p is not person and p not in person.friends]
            for friend in random.sample(potential, min(num_friends, len(potential))):
                person.friends.append(friend)
                friend.friends.append(person)

    @property
    def hour(self):
        return self.tick % DAY_LENGTH

    @property
    def time_of_day(self):
        h = self.hour
        if h < 6:    return "night"
        if h < 12:   return "morning"
        if h < 17:   return "afternoon"
        if h < 20:   return "evening"
        return "night"

    def _format_clock(self):
        h = self.hour
        period = "AM" if h < 12 else "PM"
        display_h = h % 12
        if display_h == 0:
            display_h = 12
        return f"{display_h}:00 {period}"

    def run_tick(self):
        """Advance reality by one unit of time."""
        self.tick += 1
        if self.tick % DAY_LENGTH == 0:
            self.day += 1

        events = []
        locations = {}
        for person in self.population:
            locations.setdefault(person.location, []).append(person)

        random.shuffle(self.population)
        for person in self.population:
            others = [p for p in locations.get(person.location, []) if p is not person]
            action = person.decide_action(self.hour, others)
            if action:
                events.append(action)

        return events

    def get_status_bar(self):
        awake = sum(1 for p in self.population if not p.asleep)
        avg_happy = sum(p.happiness for p in self.population) // len(self.population)
        return (
            f"Day {self.day} | {self._format_clock()} ({self.time_of_day}) | "
            f"Awake: {awake}/{len(self.population)} | "
            f"Town happiness: {avg_happy}%"
        )


# ─── Main loop (the part that makes everything go) ───────────────────────────

def print_header():
    print("\033[2J\033[H", end="")  # clear screen
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║             🏘  Welcome to Meadowbrook  🏘                  ║")
    print("║         A perfectly normal town simulation                  ║")
    print("║     (The residents are unaware this is a simulation)        ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()

def print_residents(world):
    print("  ┌─ RESIDENTS ──────────────────────────────────────────────┐")
    for p in world.population:
        status = "💤" if p.asleep else "🟢"
        print(f"  │ {status} {p.name:<20} {p.occupation:<14} @ {p.location}")
    print("  └─────────────────────────────────────────────────────────┘")
    print()

def main():
    pop = 8
    if len(sys.argv) > 1:
        try:
            pop = int(sys.argv[1])
            pop = max(2, min(pop, 12))
        except ValueError:
            pass

    world = TotallyRealWorld(population_size=pop)

    print_header()
    print("  Initializing reality...\n")
    print("  Residents of Meadowbrook:")
    for p in world.population:
        friends = ", ".join(f.first for f in p.friends[:3])
        print(f"    • {p.name} — {p.trait} {p.occupation} (friends: {friends})")
    print(f"\n  World begins at {world._format_clock()}. Press Ctrl+C to collapse reality.\n")
    time.sleep(3)

    try:
        while True:
            events = world.run_tick()

            # Print status bar
            status = world.get_status_bar()
            print(f"\033[90m{'─' * 62}\033[0m")
            print(f"  \033[1m{status}\033[0m")
            print()

            if events:
                for event in events:
                    for line in event.split("\n"):
                        print(f"  {line}")
                    print()
            else:
                tod = world.time_of_day
                if tod == "night":
                    print("  The town sleeps quietly under the stars.\n")
                else:
                    print("  A peaceful moment in Meadowbrook.\n")

            time.sleep(TICK_SPEED)

    except KeyboardInterrupt:
        print("\n")
        print("  ╔════════════════════════════════════════════════════════╗")
        print("  ║  Reality collapsed. The residents of Meadowbrook      ║")
        print("  ║  never knew. They lived, they laughed, they loved.    ║")
        print("  ║  And none of it was real. Or was it?                  ║")
        print("  ╚════════════════════════════════════════════════════════╝")
        print()

        # Final stats
        print(f"  Simulation ran for {world.day} day(s), {world.tick} ticks.")
        print(f"  Memories formed:")
        for p in world.population:
            if p.memory:
                print(f"    {p.first}: {len(p.memory)} memories")
                for m in p.memory[-3:]:
                    print(f"      - \"{m}\"")
        print()


if __name__ == "__main__":
    main()

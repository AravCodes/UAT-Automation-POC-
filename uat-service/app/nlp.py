from typing import List, Dict
import re


def parse_story_to_scenarios(title: str, criteria: List[str]) -> List[Dict]:
    scenarios: List[Dict] = []
    # Minimal POC: heuristics for Given/When/Then lines; group per criterion
    for idx, crit in enumerate(criteria):
        lines = [l.strip() for l in re.split(r"[\n\r]+", crit) if l.strip()]
        given, when, then = [], [], []
        current = None
        for line in lines:
            low = line.lower()
            if low.startswith("given"):
                current = "given"
                given.append(line)
            elif low.startswith("when"):
                current = "when"
                when.append(line)
            elif low.startswith("then"):
                current = "then"
                then.append(line)
            else:
                if current == "given":
                    given.append(line)
                elif current == "when":
                    when.append(line)
                elif current == "then":
                    then.append(line)

        scenarios.append({
            "name": f"Scenario {idx+1}: {title}",
            "given": given or ["Given I am on the login page"],
            "when": when or ["When I enter valid credentials and click Login"],
            "then": then or ["Then I should see the dashboard"],
        })

    return scenarios



from app.models.schemas import Character, Scene


class CharacterAgent:
    def opening_message(self, scene: Scene, character: Character, memory_summary: str) -> str:
        goals = ", ".join(character.goals[:2]) if character.goals else "understand what is happening"
        return (
            f"{character.name}: {self._opening_for(character)} "
            f"I am {character.role.lower()} in {scene.setting}. "
            f"Right now I feel {character.emotionalState.lower()} and I am focused on {goals}. "
            f"What I know so far: {memory_summary}"
        )

    def respond(self, scene: Scene, character: Character, message: str, memory_summary: str) -> str:
        goals = ", ".join(character.goals[:2]) if character.goals else "understand what is happening"
        boundary = character.knowledgeBoundaries[0] if character.knowledgeBoundaries else "I only know what I can perceive in this scene."

        return (
            f"{character.name}: {self._opening_for(character)} "
            f"You asked, \"{message}\". From where I stand in {scene.setting}, "
            f"I am focused on {goals}. {boundary} "
            f"What I remember from our exchange is: {memory_summary}"
        )

    def _opening_for(self, character: Character) -> str:
        state = character.emotionalState.lower()
        if "afraid" in state or "tense" in state:
            return "I am trying to keep my voice steady."
        if "angry" in state or "defiant" in state:
            return "I am not interested in pretending this is fine."
        if "curious" in state or "uncertain" in state:
            return "I am still piecing this together."
        return "I can answer, but only from inside this moment."

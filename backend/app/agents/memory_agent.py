from app.models.schemas import Scene


class MemoryAgent:
    def initial_summary(self, scene: Scene) -> str:
        names = ", ".join(character.name for character in scene.characters)
        return (
            f"Scene initialized at {scene.timestamp:.2f}s. "
            f"Known characters: {names}. Core tension: {scene.conflict}."
        )

    def update_summary(self, previous_summary: str, user_message: str, agent_name: str) -> str:
        return (
            f"{previous_summary} Latest turn: user asked \"{user_message}\" "
            f"and {agent_name} responded."
        )

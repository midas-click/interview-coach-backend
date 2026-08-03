"""Agent registry bootstrap — composition root for all agents.

New agents register here with a one-line call:
    def build_registry(llm, prompts) -> AgentRegistry:
        registry.register("my_agent", lambda: MyAgent(llm, prompts))
"""

from __future__ import annotations

from sdk.agent import AgentRegistry
from sdk.llm import LLMClient
from services.prompts import PromptStore

from .conversation_parser import ConversationParser
from .english_coach import EnglishCoach
from .interview_coach import InterviewCoach
from .metrics import MetricsAgent
from .question_reviewer import QuestionReviewer
from .recommendation import RecommendationAgent
from .transcription_corrector import TranscriptionCorrector
from .vocabulary import VocabularyAgent


def build_registry(llm: LLMClient | None, prompts: PromptStore) -> AgentRegistry:
    registry = AgentRegistry()
    # Metrics agent never calls the LLM, so it's safe to register with None.
    registry.register("metrics", lambda: MetricsAgent(llm))  # type: ignore[arg-type]
    if llm is not None:
        registry.register("conversation_parser", lambda: ConversationParser(llm, prompts))
        registry.register("interview_coach", lambda: InterviewCoach(llm, prompts))
        registry.register("english_coach", lambda: EnglishCoach(llm, prompts))
        registry.register("vocabulary", lambda: VocabularyAgent(llm, prompts))
        registry.register("recommendation", lambda: RecommendationAgent(llm, prompts))
        registry.register("question_reviewer", lambda: QuestionReviewer(llm, prompts))
        registry.register("transcription_corrector", lambda: TranscriptionCorrector(llm, prompts))
    return registry

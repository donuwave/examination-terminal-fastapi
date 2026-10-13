from typing import List, Optional

from pydantic import BaseModel, ConfigDict, model_validator

MIN_OPTIONS, MAX_OPTIONS = 2, 10


def check_question(text: str, options: List[str], correct: str) -> tuple[str, List[str], str]:
    """Приводит вопрос к чистому виду или бросает ValueError с понятным текстом."""
    text = text.strip()
    options = [item.strip() for item in options]
    correct = correct.strip()
    if not text:
        raise ValueError("Текст вопроса не может быть пустым")
    if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
        raise ValueError(f"Вариантов ответа должно быть от {MIN_OPTIONS} до {MAX_OPTIONS}")
    if any(not item for item in options):
        raise ValueError("Вариант ответа не может быть пустым")
    if len(set(options)) != len(options):
        raise ValueError("Варианты ответа не должны повторяться")
    if correct not in options:
        raise ValueError("Правильный ответ должен быть одним из вариантов")
    return text, options, correct


class QuestionBase(BaseModel):
    text_question: str
    options: List[str]
    correct_answer: str

    @model_validator(mode="after")
    def clean(self):
        self.text_question, self.options, self.correct_answer = check_question(
            self.text_question, self.options, self.correct_answer
        )
        return self


class Question(QuestionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class QuestionGet(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text_question: str
    options: List[str]
    correct_answer: str


class QuestionUpdatePartial(BaseModel):
    text_question: Optional[str] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None

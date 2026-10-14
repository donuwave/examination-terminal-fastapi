from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, model_validator

MIN_OPTIONS, MAX_OPTIONS = 2, 10
MAX_TEXT_ANSWERS = 5

Kind = Literal["single", "multiple", "text"]


def check_question(
    kind: str,
    text: str,
    options: List[str],
    correct_answer: Optional[str],
    correct_answers: Optional[List[str]],
) -> tuple[str, List[str], str, List[str]]:
    """Приводит вопрос к чистому виду или бросает ValueError с понятным текстом.

    Возвращает текст, варианты, первый верный ответ (для совместимости) и все верные ответы.
    """
    text = text.strip()
    if not text:
        raise ValueError("Текст вопроса не может быть пустым")

    # Верные ответы: список или, как раньше, один ответ строкой.
    correct = [item.strip() for item in (correct_answers or []) if item and item.strip()]
    if not correct and correct_answer and correct_answer.strip():
        correct = [correct_answer.strip()]
    if len(set(correct)) != len(correct):
        raise ValueError("Верные ответы не должны повторяться")

    if kind == "text":
        if not correct:
            raise ValueError("Укажите хотя бы один верный ответ")
        if len(correct) > MAX_TEXT_ANSWERS:
            raise ValueError(f"Допустимых ответов не больше {MAX_TEXT_ANSWERS}")
        return text, [], correct[0], correct

    options = [item.strip() for item in options]
    if not MIN_OPTIONS <= len(options) <= MAX_OPTIONS:
        raise ValueError(f"Вариантов ответа должно быть от {MIN_OPTIONS} до {MAX_OPTIONS}")
    if any(not item for item in options):
        raise ValueError("Вариант ответа не может быть пустым")
    if len(set(options)) != len(options):
        raise ValueError("Варианты ответа не должны повторяться")
    if not correct:
        raise ValueError("Отметьте правильный ответ")
    if any(item not in options for item in correct):
        raise ValueError("Правильный ответ должен быть одним из вариантов")
    if kind == "single" and len(correct) != 1:
        raise ValueError("В вопросе с одним ответом верный вариант один")
    if kind == "multiple" and len(correct) >= len(options):
        raise ValueError("Если верны все варианты, вопрос теряет смысл: оставьте хотя бы один неверный")
    return text, options, correct[0], correct


class QuestionBase(BaseModel):
    text_question: str
    kind: Kind = "single"
    options: List[str] = []
    correct_answer: Optional[str] = None
    correct_answers: Optional[List[str]] = None

    @model_validator(mode="after")
    def clean(self):
        text, options, first, correct = check_question(
            self.kind, self.text_question, self.options, self.correct_answer, self.correct_answers
        )
        self.text_question, self.options = text, options
        self.correct_answer, self.correct_answers = first, correct
        return self


class Question(QuestionBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class QuestionGet(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text_question: str
    kind: Kind = "single"
    options: List[str]
    correct_answer: str
    correct_answers: List[str] = []


class QuestionUpdatePartial(BaseModel):
    text_question: Optional[str] = None
    kind: Optional[Kind] = None
    options: Optional[List[str]] = None
    correct_answer: Optional[str] = None
    correct_answers: Optional[List[str]] = None

"""Проверка ответов. Единое место для всех типов вопросов."""

from typing import Iterable, List, Optional

SINGLE, MULTIPLE, TEXT = "single", "multiple", "text"
KINDS = (SINGLE, MULTIPLE, TEXT)


def normalize(text: str) -> str:
    """Текстовые ответы сравниваем без учёта регистра, краёв и лишних пробелов."""
    return " ".join(text.split()).casefold()


def is_answer_correct(
    kind: str,
    correct_answer: str,
    correct_answers: Iterable[str],
    student_answer: Optional[str],
    student_answers: Optional[List[str]],
) -> bool:
    correct = list(correct_answers) or [correct_answer]
    if kind == MULTIPLE:
        # Вопрос засчитывается, только если выбраны все верные варианты и ничего лишнего.
        return bool(student_answers) and set(student_answers) == set(correct)
    if kind == TEXT:
        if student_answer is None or not student_answer.strip():
            return False
        return normalize(student_answer) in {normalize(item) for item in correct}
    return student_answer is not None and student_answer == correct_answer


def given_answer(kind: str, student_answer: Optional[str], student_answers: Optional[List[str]]) -> Optional[str]:
    """Ответ студента одной строкой: для статистики и показа."""
    if kind == MULTIPLE:
        return ", ".join(sorted(student_answers)) if student_answers else None
    return student_answer

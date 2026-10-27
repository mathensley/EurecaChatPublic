from dataclasses import dataclass
from typing import Optional

@dataclass
class Context:
    token: Optional[str] = None
    user_role: str = "anon"
    user_indentifier: Optional[str] = None
    user_name: Optional[str] = None
    user_cpf: Optional[str] = None
    current_time: Optional[str] = None
    current_period: Optional[str] = None

    @property
    def is_authenticated(self) -> bool:
        return bool(self.token and self.user_indentifier)

    @property
    def normalized_user_role(self) -> str:
        role = (self.user_role or "").strip().lower()
        if role in {"aluno", "student", "estudante"}:
            return "Aluno"
        if role in {"professor", "teacher", "docente"}:
            return "Professor"
        return "anon"

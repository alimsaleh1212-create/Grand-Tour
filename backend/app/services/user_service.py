"""User lookups — pure data access, no auth logic.

Implemented in Stage 2.

Public surface (planned):
    async def get_user_by_id(
        session: AsyncSession, user_id: int
    ) -> User | None: ...

    async def get_user_by_email(
        session: AsyncSession, email: str
    ) -> User | None: ...
"""
